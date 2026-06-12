"""
Fork: persistent per-food nutrition + image data, stored in Food.extras.

Mealie's IngredientFood already has a key-value `extras` store, so foods can
carry a durable identity with no schema migration:

  nutri_per100   JSON dict of per-100g values (kcal/protein/.../sat_fat)
  nutri_source   "usda" | "off" | "manual"
  nutri_name     the matched food/product name (transparency)
  nutri_state    "user" (pinned -- never overwritten) | "auto" (estimator cache)
  image_url      product photo (OFF) or generic ingredient image (TheMealDB)

Match a food once and every recipe that uses it knows it forever.
"""

import json
import re

import httpx

NUTRI_KEYS = ["kcal", "protein", "fat", "carb", "fiber", "sugar", "sodium_mg", "chol_mg", "sat_fat"]

_MEALDB_IMG = "https://www.themealdb.com/images/ingredients/{}.png"


def read_food_nutrition(food) -> dict | None:
    """Parse the stored nutrition payload off a food's extras, or None."""
    extras = getattr(food, "extras", None) or {}
    raw = extras.get("nutri_per100")
    if not raw:
        return None
    try:
        per100 = {k: float(v) for k, v in json.loads(raw).items() if k in NUTRI_KEYS}
    except Exception:
        return None
    if not per100:
        return None
    return {
        "per100": per100,
        "source": extras.get("nutri_source") or "manual",
        "name": extras.get("nutri_name") or None,
        "state": extras.get("nutri_state") or "auto",
        "image_url": extras.get("image_url") or None,
    }


def write_food_nutrition(
    repos,
    food_id,
    *,
    per100: dict,
    source: str,
    name: str | None,
    state: str,
    image_url: str | None = None,
) -> bool:
    """Persist nutrition data onto the food. Auto writes never clobber a
    user-pinned match; user writes always win. Returns True if written."""
    food = repos.ingredient_foods.get_one(food_id)
    if food is None:
        return False
    extras = dict(food.extras or {})
    if state == "auto" and extras.get("nutri_state") == "user":
        return False
    extras["nutri_per100"] = json.dumps({k: round(float(per100.get(k, 0)), 3) for k in NUTRI_KEYS})
    extras["nutri_source"] = source
    extras["nutri_name"] = name or ""
    extras["nutri_state"] = state
    if image_url:
        extras["image_url"] = image_url
    food.extras = extras
    repos.ingredient_foods.update(food_id, food)
    return True


def clear_food_nutrition(repos, food_id) -> bool:
    food = repos.ingredient_foods.get_one(food_id)
    if food is None:
        return False
    extras = dict(food.extras or {})
    for key in ("nutri_per100", "nutri_source", "nutri_name", "nutri_state", "image_url"):
        extras.pop(key, None)
    food.extras = extras
    repos.ingredient_foods.update(food_id, food)
    return True


async def mealdb_image(client: httpx.AsyncClient, food_name: str) -> str | None:
    """Generic ingredient image from TheMealDB's free CDN (clean white-background
    PNGs). Tries the cleaned full name, then the last word ("chicken thighs" ->
    "thighs" misses but "yellow onion" -> "onion" hits)."""
    cleaned = re.sub(r"\([^)]*\)", "", food_name).split(",")[0].strip().lower()
    candidates = [cleaned]
    words = cleaned.split()
    if len(words) > 1:
        candidates.append(words[-1])
    for term in candidates:
        if not term:
            continue
        try:
            resp = await client.head(_MEALDB_IMG.format(term), timeout=5.0, follow_redirects=True)
            if resp.status_code == 200:
                return _MEALDB_IMG.format(term)
        except Exception:
            continue
    return None
