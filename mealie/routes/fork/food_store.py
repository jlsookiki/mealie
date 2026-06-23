"""
Fork: persistent per-food nutrition + image data, stored in Food.extras.

Mealie's IngredientFood already has a key-value `extras` store, so foods can
carry a durable identity with no schema migration:

  nutri_per100         JSON dict of per-100g values (kcal/protein/.../sat_fat)
  nutri_source         provider tag for the chip: usda | off | nutritionix | manual
  nutri_source_detail  free-text citation, e.g. "USDA FDC #11215",
                       "A Dozen Cousins package label", "Claude estimate"
  nutri_authority      trust tier: official > manual > estimate (see AUTHORITY_RANK)
  nutri_name           the matched food/product name (transparency)
  nutri_state          "user" (pinned -- never auto-overwritten) | "auto" (estimator cache)
  image_url            product photo (OFF) or generic ingredient image (TheMealDB)

Match a food once and every recipe that uses it knows it forever. Overrides
carry their provenance so a low-confidence guess is visibly distinct from an
official, cited value -- and can never silently replace one (see the guard in
food_data.py).
"""

import json
import re

import httpx

from mealie.schema.recipe.recipe_ingredient import SaveIngredientFood

NUTRI_KEYS = ["kcal", "protein", "fat", "carb", "fiber", "sugar", "sodium_mg", "chol_mg", "sat_fat"]

# Trust hierarchy for stored nutrition. Higher wins; an "estimate" must never
# silently overwrite "official"/"manual" data (the "prefer an official one" rule).
AUTHORITY_RANK = {"official": 3, "manual": 2, "estimate": 1}

# Providers whose data is an official/cited source by nature.
_OFFICIAL_SOURCES = {"usda", "off", "nutritionix"}

_MEALDB_IMG = "https://www.themealdb.com/images/ingredients/{}.png"


def _default_authority(source: str) -> str:
    """Authority for legacy records written before the field existed."""
    return "official" if source in _OFFICIAL_SOURCES else "manual"


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
    source = extras.get("nutri_source") or "manual"
    authority = extras.get("nutri_authority") or _default_authority(source)
    return {
        "per100": per100,
        "source": source,
        "sourceDetail": extras.get("nutri_source_detail") or None,
        "authority": authority,
        "name": extras.get("nutri_name") or None,
        "state": extras.get("nutri_state") or "auto",
        "image_url": extras.get("image_url") or None,
    }


def write_food_nutrition(
    repos,
    food_id,
    *,
    group_id,
    per100: dict,
    source: str,
    name: str | None,
    state: str,
    authority: str = "manual",
    source_detail: str | None = None,
    image_url: str | None = None,
) -> bool:
    """Persist nutrition data onto the food. Auto writes never clobber a
    user-pinned match; user writes always win. Returns True if written.

    Note: the *authority downgrade* guard (an estimate cannot replace
    official/manual data) lives in the route layer, which can return a 409;
    this function is the low-level writer and trusts its caller."""
    food = repos.ingredient_foods.get_one(food_id)
    if food is None:
        return False
    extras = dict(food.extras or {})
    if state == "auto" and extras.get("nutri_state") == "user":
        return False
    extras["nutri_per100"] = json.dumps({k: round(float(per100.get(k, 0)), 3) for k in NUTRI_KEYS})
    extras["nutri_source"] = source
    extras["nutri_authority"] = authority if authority in AUTHORITY_RANK else _default_authority(source)
    extras["nutri_name"] = name or ""
    extras["nutri_state"] = state
    if source_detail is not None:
        extras["nutri_source_detail"] = source_detail
    if image_url:
        extras["image_url"] = image_url
    food.extras = extras
    # The repo layer needs group_id in the payload (same cast the core foods
    # PUT route does), or the DB model re-init blows up.
    repos.ingredient_foods.update(food_id, food.cast(SaveIngredientFood, group_id=group_id))
    return True


def clear_food_nutrition(repos, food_id, group_id) -> bool:
    food = repos.ingredient_foods.get_one(food_id)
    if food is None:
        return False
    extras = dict(food.extras or {})
    for key in (
        "nutri_per100", "nutri_source", "nutri_source_detail", "nutri_authority",
        "nutri_name", "nutri_state", "image_url",
    ):
        extras.pop(key, None)
    food.extras = extras
    repos.ingredient_foods.update(food_id, food.cast(SaveIngredientFood, group_id=group_id))
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
