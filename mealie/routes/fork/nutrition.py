"""
Fork-specific route: POST /api/fork/nutrition

Given a recipe's parsed ingredients + serving count, looks up nutrition from
three sources concurrently — USDA FoodData Central, Open Food Facts, and
(when configured) Nutritionix — cross-references them per ingredient, converts
to grams, sums totals, divides by servings, and returns per-serving nutrition
with a per-ingredient breakdown that includes every source's value.

Cross-referencing:
- Each source returns its top candidates (not just the first hit).
- Candidates are scored: query-token overlap dominates, then source quality
  (USDA Foundation > SR Legacy > Branded for generics; OFF scan count and
  completeness), plus a consensus bonus for kcal values near the candidate
  median. Highest score wins.
- Disagreement beyond 25% across the sources' best picks is flagged so a
  wrong match is visible.
"""

import asyncio
import re
from typing import Any

import httpx
from fastapi import APIRouter

from mealie.routes._base import BaseUserController, controller

from .food_store import read_food_nutrition, write_food_nutrition

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
    food_id: str | None = None  # links to a Mealie food: enables pinned data + write-back


class NutritionEstimateRequest(BaseModel):
    ingredients: list[IngredientIn]
    servings: float


class SourceValue(BaseModel):
    """One source's match for an ingredient, for cross-referencing."""
    source: str  # "usda" | "off" | "nutritionix"
    name: str | None = None
    kcalPer100: int | None = None


class AlternativeOut(BaseModel):
    """A ranked candidate the user can swap to; per100 lets the client recompute totals."""
    source: str
    name: str | None = None
    kcal: int | None = None  # kcal for this row's grams, ready to display
    per100: dict[str, float]  # kcal/protein/fat/carb/fiber/sugar/sodium_mg/chol_mg/sat_fat


class IngredientBreakdown(BaseModel):
    input: str
    grams: int | None
    source: str | None  # primary source used for the totals
    kcal: int | None
    matched: str | None = None  # name of the matched food, for transparency
    sources: list[SourceValue] = []  # every source that returned a value
    agreement: str | None = None  # "single" | "agree" | "divergent" | None
    alternatives: list[AlternativeOut] = []  # top-ranked candidates, primary first


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
_NUTRITIONIX_URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"


def _parse_usda_foods(data: dict) -> list[dict]:
    """Parse every returned food into a per-100g candidate, keeping ranking metadata."""
    candidates: list[dict] = []
    for food in data.get("foods") or []:
        by_num: dict[str, float] = {}
        for n in food.get("foodNutrients") or []:
            num = n.get("nutrientNumber")
            if num is not None:
                by_num[str(num)] = float(n.get("value") or 0)
        # Foundation foods report energy as Atwater factors (#957/#958), not #208 —
        # requiring #208 silently rejected USDA's lab-analyzed gold-standard data.
        kcal = by_num.get("208") or by_num.get("957") or by_num.get("958") or 0
        # Zero-kcal foods (salt!) are real: keep them when other nutrients exist,
        # else "salt" can only ever match caloric salted foods like butter.
        if not kcal and not any(by_num.get(n) for n in ("203", "204", "205", "307")):
            continue
        candidates.append({
            "name": str(food.get("description") or "").strip().title(),
            "kcal": kcal,
            "protein": by_num.get("203", 0),
            "fat": by_num.get("204", 0),
            "carb": by_num.get("205", 0),
            "fiber": by_num.get("291", 0),
            "sugar": by_num.get("269") or by_num.get("2000", 0),
            "sodium_mg": by_num.get("307", 0),
            "chol_mg": by_num.get("601", 0),
            "sat_fat": by_num.get("606", 0),
            "dataType": food.get("dataType"),
        })
    return candidates


def _parse_off_products(data: dict) -> list[dict]:
    """Parse every returned product into a per-100g candidate, keeping crowd-quality metadata."""
    candidates: list[dict] = []
    for product in data.get("products") or []:
        n = product.get("nutriments") or {}

        def _f(key: str, _n: dict = n) -> float:
            return float(_n.get(key) or 0)

        kcal = _f("energy-kcal_100g")
        if not kcal and not any(_f(k) for k in ("proteins_100g", "fat_100g", "carbohydrates_100g", "sodium_100g")):
            continue
        name = str(product.get("product_name") or product.get("product_name_en") or "").strip()
        brand = str(product.get("brands") or "").split(",")[0].strip()
        candidates.append({
            "name": f"{name} ({brand})" if brand and brand.lower() not in name.lower() else name,
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
            # crowd-verification signals: scan count separates OFF's good data from junk
            "scans": float(product.get("unique_scans_n") or 0),
            "completeness": float(product.get("completeness") or 0),
            "image": product.get("image_front_small_url") or product.get("image_front_url") or None,
        })
    return candidates


async def _lookup_usda(
    client: httpx.AsyncClient,
    term: str,
    api_key: str,
    data_types: str = "Foundation,SR Legacy",
) -> list[dict]:
    try:
        resp = await client.get(
            _USDA_URL,
            params={"query": term, "pageSize": 5, "dataType": data_types, "api_key": api_key},
            timeout=8.0,
        )
        resp.raise_for_status()
        return _parse_usda_foods(resp.json())
    except Exception:
        return []


async def _off_search(client: httpx.AsyncClient, term: str) -> dict | None:
    """One OFF search with a single retry on transient 5xx (their API is flaky)."""
    for attempt in range(2):
        try:
            resp = await client.get(
                _OFF_URL,
                params={"search_terms": term, "search_simple": 1, "action": "process", "json": 1, "page_size": 5},
                headers=_OFF_HEADERS,
                timeout=8.0,
            )
            if resp.status_code >= 500 and attempt == 0:
                await asyncio.sleep(0.4)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt == 0:
                await asyncio.sleep(0.4)
                continue
            return None
    return None


async def _lookup_off(client: httpx.AsyncClient, term: str) -> list[dict]:
    data = await _off_search(client, term)
    result = _parse_off_products(data) if data else []
    if not result and len(term.split()) > 4:
        # retry with first 4 words for long branded names
        short = " ".join(term.split()[:4])
        data = await _off_search(client, short)
        result = _parse_off_products(data) if data else []
    return result


def _parse_nutritionix(data: dict) -> dict | None:
    foods = data.get("foods") or []
    if not foods:
        return None
    food = foods[0]
    swg = float(food.get("serving_weight_grams") or 0)
    kcal_serv = float(food.get("nf_calories") or 0)
    if not swg or not kcal_serv:
        return None
    # Nutritionix returns nutrients for the parsed serving; normalize to per-100g.
    f = 100.0 / swg

    def _n(key: str) -> float:
        return float(food.get(key) or 0) * f

    name = str(food.get("food_name") or "").strip().title()
    brand = str(food.get("brand_name") or "").strip()
    return {
        "name": f"{name} ({brand})" if brand and brand.lower() not in name.lower() else name,
        "kcal": kcal_serv * f,
        "protein": _n("nf_protein"),
        "fat": _n("nf_total_fat"),
        "carb": _n("nf_total_carbohydrate"),
        "fiber": _n("nf_dietary_fiber"),
        "sugar": _n("nf_sugars"),
        "sodium_mg": _n("nf_sodium"),  # already mg
        "chol_mg": _n("nf_cholesterol"),  # already mg
        "sat_fat": _n("nf_saturated_fat"),
    }


async def _lookup_nutritionix(client: httpx.AsyncClient, term: str, app_id: str, app_key: str) -> dict | None:
    """Nutritionix natural-language nutrients endpoint. Returns None if unconfigured."""
    if not app_id or not app_key:
        return None
    try:
        resp = await client.post(
            _NUTRITIONIX_URL,
            json={"query": term},
            headers={"x-app-id": app_id, "x-app-key": app_key, "Content-Type": "application/json"},
            timeout=8.0,
        )
        resp.raise_for_status()
        return _parse_nutritionix(resp.json())
    except Exception:
        return None


async def _lookup_candidates(
    client: httpx.AsyncClient,
    query: str,
    usda_key: str,
    nx_id: str,
    nx_key: str,
) -> tuple[list[dict], bool]:
    """Query every available source concurrently for top candidates.

    Each candidate is a per-100g dict tagged with its "source" plus quality
    metadata (USDA dataType, OFF scan count/completeness) used for scoring."""
    term = _clean_query(query) or query
    branded = _looks_branded(query)
    usda_types = "Branded,Foundation,SR Legacy" if branded else "Foundation,SR Legacy"

    usda, off, nx = await asyncio.gather(
        _lookup_usda(client, term, usda_key, data_types=usda_types),
        _lookup_off(client, term),
        _lookup_nutritionix(client, term, nx_id, nx_key),
    )

    candidates: list[dict] = []
    for src, results in (("usda", usda), ("off", off), ("nutritionix", [nx] if nx else [])):
        for rank, per100 in enumerate(results):
            if per100:
                candidates.append({**per100, "source": src, "rank": rank})
    return candidates, branded


_TOKEN_STOPWORDS = {"a", "an", "the", "of", "in", "with", "and", "or", "to", "for", "each"}


def _tokens(s: str) -> set[str]:
    """Lowercased word set, articles dropped, naive singularization (chickpeas → chickpea)."""
    out = set()
    for t in re.split(r"[^a-z]+", s.lower()):
        if len(t) < 2 or t in _TOKEN_STOPWORDS:
            continue
        if len(t) > 3 and t.endswith("es"):
            t = t[:-2]
        elif len(t) > 2 and t.endswith("s"):
            t = t[:-1]
        out.add(t)
    return out


_USDA_TYPE_BONUS = {"Foundation": 0.30, "SR Legacy": 0.20, "Branded": 0.10}

# Preparation/state/size words: real signal for choosing BETWEEN variants of a
# food, but worthless for identifying WHICH food. "Basil, Fresh" must never
# match "fresh ginger" on the strength of "fresh" alone.
_DESCRIPTOR_TOKENS = {
    "fresh", "raw", "cooked", "dried", "ground", "grated", "chopped", "sliced",
    "minced", "diced", "peeled", "frozen", "canned", "whole", "large", "small",
    "medium", "ripe", "root", "boneless", "skinless", "lean", "salted",
    "unsalted", "sweetened", "unsweetened", "extra", "light",
}


def _score_candidate(c: dict, query_tokens: set[str], branded: bool) -> float:
    """Match confidence: token overlap with the query dominates; source quality breaks ties.

    - Token overlap is F1-style: recall of the query AND precision of the name, so
      "Almond Butter" (contains "butter" but is a different food) scores below plain
      "Butter, salted". Parenthetical synonyms are stripped first — USDA's
      "(garbanzo beans, bengal gram)" decorations aren't noise to punish.
    - An exact head-noun match (first comma-segment == query) earns a bonus, matching
      USDA's "Head, qualifiers, ..." naming convention.
    - Each API's own relevance ordering earns a small rank bonus.
    - USDA: trust ladder Foundation (lab-analyzed) > SR Legacy > Branded (label data);
      inverted for branded queries where the Branded dataset is the right shelf.
    - OFF: crowd verification — unique scan count (2 scans = junk, 95 = trustworthy)
      plus the dataset's own completeness score.
    """
    raw_name = c.get("name") or ""
    clean_name = re.sub(r"\([^)]*\)", "", raw_name)
    name_tokens = _tokens(clean_name)
    if not query_tokens or not name_tokens:
        return 0.0

    # Identity match: F1 over food-identity tokens only. Falls back to all
    # tokens when either side is pure descriptors (degenerate queries).
    q_id = query_tokens - _DESCRIPTOR_TOKENS
    n_id = name_tokens - _DESCRIPTOR_TOKENS
    if not q_id or not n_id:
        q_id, n_id = query_tokens, name_tokens
    hits = len(q_id & n_id)
    if not hits:
        return 0.0  # no shared identity word — descriptors alone can't match
    precision = hits / len(n_id)
    recall = hits / len(q_id)
    score = 2 * precision * recall / (precision + recall)

    # Descriptor agreement as a gentle tiebreak (fresh vs dried vs ground).
    q_desc = query_tokens & _DESCRIPTOR_TOKENS
    if q_desc:
        score += 0.08 * len(q_desc & name_tokens) / len(q_desc)

    if (_tokens(clean_name.split(",")[0]) - _DESCRIPTOR_TOKENS or set()) == q_id:
        score += 0.15
    score += max(0.0, 0.10 - 0.025 * (c.get("rank") or 0))

    if c["source"] == "usda":
        if branded:
            score += 0.25 if c.get("dataType") == "Branded" else 0.10
        else:
            score += _USDA_TYPE_BONUS.get(c.get("dataType") or "", 0.05)
    elif c["source"] == "off":
        scans = min(c.get("scans") or 0.0, 100.0) / 100.0
        score += 0.20 * scans + 0.10 * (c.get("completeness") or 0.0)
    elif c["source"] == "nutritionix":
        score += 0.20
    return score


def _select_primary(
    candidates: list[dict], branded: bool, query: str
) -> tuple[dict | None, str, list[dict], list[dict]]:
    """Score all candidates → (primary, agreement, best-per-source, ranked).

    The consensus bonus requires true cross-referencing: a candidate only earns it
    when a candidate from a DIFFERENT source lands within 25% kcal — same-source
    neighbors agreeing means nothing, and a global median is meaningless when the
    kcal distribution is bimodal (canned ~130 vs dry ~380 chickpeas). Agreement is
    judged across each source's best candidate: "single" | "agree" | "divergent"."""
    if not candidates:
        return None, "none", [], []

    query_tokens = _tokens(_clean_query(query) or query)
    scored = []
    for c in candidates:
        s = _score_candidate(c, query_tokens, branded)
        corroborated = any(
            o["source"] != c["source"] and abs(o["kcal"] - c["kcal"]) / max(c["kcal"], 1) <= 0.25
            for o in candidates
        )
        if corroborated:
            s += 0.25
        scored.append((c, s))

    # An honest "no match" beats a confident wrong one: drop candidates that
    # never cleared the identity bar (0.0 base + at most the consensus bonus).
    scored = [(c, s) for c, s in scored if s > 0.30]
    if not scored:
        return None, "none", [], []

    best_per_source: dict[str, tuple[dict, float]] = {}
    for c, s in scored:
        cur = best_per_source.get(c["source"])
        if cur is None or s > cur[1]:
            best_per_source[c["source"]] = (c, s)

    ranked = [c for c, _ in sorted(scored, key=lambda cs: cs[1], reverse=True)]
    primary = ranked[0]

    source_bests = [c for c, _ in best_per_source.values()]
    if len(source_bests) == 1:
        agreement = "single"
    else:
        kcals = sorted(c["kcal"] for c in source_bests)
        mid = kcals[len(kcals) // 2]
        agreement = "agree" if (kcals[-1] - kcals[0]) / max(mid, 1) <= 0.25 else "divergent"

    return primary, agreement, source_bests, ranked


_NUTRIENT_KEYS = ["kcal", "protein", "fat", "carb", "fiber", "sugar", "sodium_mg", "chol_mg", "sat_fat"]


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
        nx_id = self.settings.NUTRITIONIX_APP_ID
        nx_key = self.settings.NUTRITIONIX_APP_KEY
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

            # Pinned food data short-circuits the live lookup entirely: the
            # user confirmed this match once, so it's deterministic forever.
            stored = None
            if ing.food_id:
                try:
                    food_row = self.repos.ingredient_foods.get_one(ing.food_id)
                    stored = read_food_nutrition(food_row) if food_row else None
                except Exception:
                    stored = None
            if stored and stored["state"] == "user":
                f = grams / 100.0
                per100 = stored["per100"]
                async with lock:
                    for k in totals:
                        totals[k] += per100.get(k, 0) * f
                    breakdown.append(IngredientBreakdown(
                        input=query,
                        grams=int(round(grams)),
                        source=stored["source"],
                        kcal=int(round(per100.get("kcal", 0) * f)),
                        matched=stored["name"],
                        agreement="pinned",
                        alternatives=[AlternativeOut(
                            source=stored["source"], name=stored["name"],
                            kcal=int(round(per100.get("kcal", 0) * f)),
                            per100={k: float(per100.get(k, 0)) for k in totals},
                        )],
                    ))
                return

            candidates, branded = await _lookup_candidates(client, query, api_key, nx_id, nx_key)
            primary, agreement, source_bests, ranked = _select_primary(candidates, branded, query)

            sources_out = [
                SourceValue(source=c["source"], name=c.get("name") or None, kcalPer100=int(round(c["kcal"])))
                for c in sorted(source_bests, key=lambda c: c["kcal"])
            ]

            f = grams / 100.0
            alternatives: list[AlternativeOut] = []
            seen_alts: set[tuple[str, str]] = set()
            for c in ranked:
                alt_key = (c["source"], (c.get("name") or "").lower())
                if alt_key in seen_alts:
                    continue
                seen_alts.add(alt_key)
                alternatives.append(AlternativeOut(
                    source=c["source"],
                    name=c.get("name") or None,
                    kcal=int(round(c["kcal"] * f)),
                    per100={k: round(float(c.get(k, 0)), 3) for k in _NUTRIENT_KEYS},
                ))
                if len(alternatives) == 3:
                    break

            if primary is None:
                async with lock:
                    breakdown.append(IngredientBreakdown(
                        input=query,
                        grams=int(round(grams)),
                        source=None,
                        kcal=None,
                        agreement="none",
                    ))
                return

            async with lock:
                for k in totals:
                    totals[k] += primary.get(k, 0) * f
                breakdown.append(IngredientBreakdown(
                    input=query,
                    grams=int(round(grams)),
                    source=primary["source"],
                    kcal=int(round(primary["kcal"] * f)),
                    matched=primary.get("name") or None,
                    sources=sources_out,
                    agreement=agreement,
                    alternatives=alternatives,
                ))
                # Self-building food database: cache the auto-match on the food
                # (never clobbers a user-pinned entry).
                if ing.food_id:
                    try:
                        write_food_nutrition(
                            self.repos, ing.food_id, group_id=self.group_id,
                            per100={k: float(primary.get(k, 0)) for k in totals},
                            source=primary["source"],
                            name=primary.get("name"),
                            state="auto",
                            authority="official",
                            source_detail=f"Auto-matched: {primary.get('name') or primary['source']}",
                            image_url=primary.get("image"),
                        )
                    except Exception:
                        pass  # caching is best-effort; the estimate itself succeeded

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
