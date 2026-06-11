"""
Fork-specific route: POST /api/fork/nutrition

Given a recipe's parsed ingredients + serving count, looks up nutrition from
USDA FoodData Central (generic foods) and Open Food Facts (branded/packaged),
converts each ingredient to grams, sums totals, divides by servings, and
returns per-serving nutrition with a per-ingredient breakdown.

Source routing:
- looksBranded → try OFF first, USDA fallback
- generic → try USDA first, OFF fallback
"""

import asyncio
import re
from typing import Any

import httpx
from fastapi import APIRouter

from mealie.routes._base import BaseUserController, controller

router = APIRouter(prefix="/fork")

# ---------------------------------------------------------------------------
# Gram-conversion tables (ported from use-nutrition-estimate.ts)
# ---------------------------------------------------------------------------

MASS_G: dict[str, float] = {
    "g": 1, "gram": 1, "grams": 1, "gm": 1,
    "kg": 1000, "kilogram": 1000,
    "mg": 0.001,
    "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,
    "lb": 453.592, "lbs": 453.592, "pound": 453.592, "pounds": 453.592,
}

VOL_ML: dict[str, float] = {
    "ml": 1, "milliliter": 1, "milliliters": 1,
    "l": 1000, "liter": 1000, "liters": 1000,
    "tsp": 4.92892, "teaspoon": 4.92892, "teaspoons": 4.92892,
    "tbsp": 14.7868, "tablespoon": 14.7868, "tablespoons": 14.7868,
    "cup": 236.588, "cups": 236.588,
    "fl oz": 29.5735, "fluid ounce": 29.5735,
    "pint": 473.176, "pints": 473.176,
    "quart": 946.353, "quarts": 946.353,
    "gallon": 3785.41,
}

# (regex, g/ml density)
DENSITY: list[tuple[re.Pattern, float]] = [
    (re.compile(r"oil|butter|ghee|tahini"), 0.91),
    (re.compile(r"flour|cocoa|powder"), 0.55),
    (re.compile(r"sugar|honey|syrup|molasses"), 0.85),
    (re.compile(r"rice|grain|oat|quinoa|lentil"), 0.85),
    (re.compile(r"milk|cream|yogurt|broth|stock|water|juice|wine|vinegar|sauce"), 1.0),
    (re.compile(r"salt"), 1.2),
]

# (regex, grams per count)
COUNT_G: list[tuple[re.Pattern, float]] = [
    (re.compile(r"clove"), 3),
    (re.compile(r"egg"), 50),
    (re.compile(r"onion|pepper|apple|potato|orange"), 130),
    (re.compile(r"lemon|lime|tomato|peach|carrot"), 100),
    (re.compile(r"cucumber"), 200),
    (re.compile(r"banana"), 120),
    (re.compile(r"can\b|tin\b"), 400),
    (re.compile(r"packet|package|pouch|jar"), 250),
    (re.compile(r"slice"), 25),
    (re.compile(r"sprig|leaf"), 3),
]

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

from pydantic import BaseModel  # noqa: E402 (after stdlib imports)


class IngredientIn(BaseModel):
    quantity: float | None = None
    unit: dict[str, Any] | str | None = None
    food: dict[str, Any] | str | None = None
    note: str | None = None


class NutritionEstimateRequest(BaseModel):
    ingredients: list[IngredientIn]
    servings: float


class IngredientBreakdown(BaseModel):
    input: str
    grams: int | None
    source: str | None  # "usda" | "off" | None
    kcal: int | None


class NutritionOut(BaseModel):
    calories: str
    proteinContent: str
    fatContent: str
    carbohydrateContent: str
    fiberContent: str
    sugarContent: str
    sodiumContent: str
    cholesterolContent: str
    saturatedFatContent: str


class NutritionEstimateResponse(BaseModel):
    nutrition: NutritionOut
    breakdown: list[IngredientBreakdown]
    servings: int
    matched: int
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(s: Any) -> str:
    return str(s or "").lower().strip().rstrip(".")


def _to_grams(qty: float | None, unit_name: str, food_name: str) -> float:
    q = qty if qty and qty > 0 else 1.0
    u = _norm(unit_name)
    food = _norm(food_name)

    if not u:
        for pattern, g in COUNT_G:
            if pattern.search(food):
                return q * g
        return q * 100.0

    if u in MASS_G:
        return q * MASS_G[u]

    if u in VOL_ML:
        density = 1.0
        for pattern, d in DENSITY:
            if pattern.search(food):
                density = d
                break
        return q * VOL_ML[u] * density

    # count unit that matches a keyword
    for pattern, g in COUNT_G:
        if pattern.search(u) or pattern.search(food):
            return q * g

    return q * 100.0


def _clean_query(q: str) -> str:
    """Strip parentheticals, trailing prep notes, stray sizes, collapse whitespace."""
    q = re.sub(r"\([^)]*\)", "", q)
    q = q.split(",")[0]
    q = re.sub(r"\b\d+(\.\d+)?\s*(oz|g|ml|lb|kg|pound|ounce|gram)s?\b", "", q, flags=re.IGNORECASE)
    return q.strip()


def _looks_branded(query: str) -> bool:
    """True if query looks like a packaged/branded product."""
    # parenthetical containing a unit → e.g. "(8 oz each)"
    if re.search(r"\([^)]*\b(oz|lb|g|kg|ml)\b[^)]*\)", query, re.IGNORECASE):
        return True
    # two or more Capitalized words (Title Case proper nouns → brand names)
    caps = re.findall(r"\b[A-Z][a-z]+\b", query)
    return len(caps) >= 2


# ---------------------------------------------------------------------------
# API look-ups
# ---------------------------------------------------------------------------

_USDA_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
_OFF_URL = "https://world.openfoodfacts.org/cgi/search.pl"
_OFF_HEADERS = {"User-Agent": "MealieFork/1.0"}


def _parse_usda(data: dict) -> dict | None:
    food = (data.get("foods") or [None])[0]
    if not food:
        return None
    by_num: dict[str, float] = {}
    for n in food.get("foodNutrients") or []:
        num = n.get("nutrientNumber")
        if num is not None:
            by_num[str(num)] = float(n.get("value") or 0)
    kcal = by_num.get("208", 0)
    if not kcal:
        return None
    return {
        "kcal": kcal,
        "protein": by_num.get("203", 0),
        "fat": by_num.get("204", 0),
        "carb": by_num.get("205", 0),
        "fiber": by_num.get("291", 0),
        "sugar": by_num.get("269") or by_num.get("2000", 0),
        "sodium_mg": by_num.get("307", 0),
        "chol_mg": by_num.get("601", 0),
        "sat_fat": by_num.get("606", 0),
    }


def _parse_off(data: dict) -> dict | None:
    products = data.get("products") or []
    if not products:
        return None
    n = products[0].get("nutriments") or {}

    def _f(key: str) -> float:
        return float(n.get(key) or 0)

    kcal = _f("energy-kcal_100g")
    if not kcal:
        return None
    return {
        "kcal": kcal,
        "protein": _f("proteins_100g"),
        "fat": _f("fat_100g"),
        "carb": _f("carbohydrates_100g"),
        "fiber": _f("fiber_100g"),
        "sugar": _f("sugars_100g"),
        # OFF sodium is in grams/100g → convert to mg
        "sodium_mg": _f("sodium_100g") * 1000,
        "chol_mg": _f("cholesterol_100g") * 1000,
        "sat_fat": _f("saturated-fat_100g"),
    }


async def _lookup_usda(client: httpx.AsyncClient, term: str, api_key: str) -> dict | None:
    try:
        resp = await client.get(
            _USDA_URL,
            params={"query": term, "pageSize": 1, "dataType": "Foundation,SR Legacy", "api_key": api_key},
            timeout=8.0,
        )
        resp.raise_for_status()
        return _parse_usda(resp.json())
    except Exception:
        return None


async def _lookup_off(client: httpx.AsyncClient, term: str) -> dict | None:
    try:
        resp = await client.get(
            _OFF_URL,
            params={"search_terms": term, "search_simple": 1, "action": "process", "json": 1, "page_size": 1},
            headers=_OFF_HEADERS,
            timeout=8.0,
        )
        resp.raise_for_status()
        data = resp.json()
        result = _parse_off(data)
        if result is None and len(term.split()) > 4:
            # retry with first 4 words for long branded names
            short = " ".join(term.split()[:4])
            resp2 = await client.get(
                _OFF_URL,
                params={"search_terms": short, "search_simple": 1, "action": "process", "json": 1, "page_size": 1},
                headers=_OFF_HEADERS,
                timeout=8.0,
            )
            resp2.raise_for_status()
            result = _parse_off(resp2.json())
        return result
    except Exception:
        return None


async def _lookup_food(
    client: httpx.AsyncClient,
    query: str,
    api_key: str,
) -> tuple[dict, str] | None:
    """Return (per100, source) or None. Routes branded → OFF first, generic → USDA first."""
    term = _clean_query(query) or query
    branded = _looks_branded(query)

    if branded:
        per100 = await _lookup_off(client, term)
        if per100:
            return per100, "off"
        per100 = await _lookup_usda(client, term, api_key)
        if per100:
            return per100, "usda"
    else:
        per100 = await _lookup_usda(client, term, api_key)
        if per100:
            return per100, "usda"
        per100 = await _lookup_off(client, term)
        if per100:
            return per100, "off"

    return None


def _round1(n: float) -> str:
    return str(round(n, 1))


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


@controller(router)
class ForkNutritionController(BaseUserController):
    @router.post("/nutrition", response_model=NutritionEstimateResponse)
    async def estimate_nutrition(self, body: NutritionEstimateRequest) -> NutritionEstimateResponse:
        """
        Estimate per-serving nutrition for a list of parsed ingredients.
        Looks up USDA FoodData Central and Open Food Facts concurrently.
        """
        api_key = self.settings.USDA_API_KEY
        servings = max(1, int(round(body.servings))) if body.servings and body.servings > 0 else 1

        totals: dict[str, float] = {
            "kcal": 0, "protein": 0, "fat": 0, "carb": 0, "fiber": 0,
            "sugar": 0, "sodium_mg": 0, "chol_mg": 0, "sat_fat": 0,
        }
        breakdown: list[IngredientBreakdown] = []
        lock = asyncio.Lock()

        async def process_ingredient(ing: IngredientIn) -> None:
            food_raw = ing.food
            food_name: str = (
                food_raw if isinstance(food_raw, str)
                else (food_raw.get("name") or "" if isinstance(food_raw, dict) else "")
            )
            unit_raw = ing.unit
            unit_name: str = (
                unit_raw if isinstance(unit_raw, str)
                else (unit_raw.get("name") or "" if isinstance(unit_raw, dict) else "")
            )
            query = (food_name or ing.note or "").strip()

            if not query:
                async with lock:
                    breakdown.append(IngredientBreakdown(
                        input=ing.note or "",
                        grams=None,
                        source=None,
                        kcal=None,
                    ))
                return

            grams = _to_grams(ing.quantity, unit_name, food_name or ing.note or "")
            hit = await _lookup_food(client, query, api_key)

            if hit is None:
                async with lock:
                    breakdown.append(IngredientBreakdown(
                        input=query,
                        grams=int(round(grams)),
                        source=None,
                        kcal=None,
                    ))
                return

            per100, source = hit
            f = grams / 100.0
            async with lock:
                for k in totals:
                    totals[k] += per100.get(k, 0) * f
                breakdown.append(IngredientBreakdown(
                    input=query,
                    grams=int(round(grams)),
                    source=source,
                    kcal=int(round(per100["kcal"] * f)),
                ))

        async with httpx.AsyncClient() as client:
            await asyncio.gather(*[process_ingredient(ing) for ing in body.ingredients])

        s = float(servings)
        nutrition = NutritionOut(
            calories=_round1(totals["kcal"] / s),
            proteinContent=_round1(totals["protein"] / s),
            fatContent=_round1(totals["fat"] / s),
            carbohydrateContent=_round1(totals["carb"] / s),
            fiberContent=_round1(totals["fiber"] / s),
            sugarContent=_round1(totals["sugar"] / s),
            sodiumContent=_round1(totals["sodium_mg"] / s),
            cholesterolContent=_round1(totals["chol_mg"] / s),
            saturatedFatContent=_round1(totals["sat_fat"] / s),
        )
        matched = sum(1 for b in breakdown if b.source is not None)

        return NutritionEstimateResponse(
            nutrition=nutrition,
            breakdown=breakdown,
            servings=servings,
            matched=matched,
            total=len(body.ingredients),
        )
