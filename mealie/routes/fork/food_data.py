"""
Fork: per-food nutrition endpoints — the "Ingredient Intelligence" API.

  POST /api/fork/foods/{food_id}/search     live USDA+OFF candidate search
                                            (scored, with images) for the food
  PUT  /api/fork/foods/{food_id}/nutrition  pin a match or manual values
  DELETE /api/fork/foods/{food_id}/nutrition  clear stored data

Reading needs no endpoint: stored data rides along in food.extras on every
recipe/food response.
"""

import asyncio

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from mealie.routes._base import BaseUserController, controller
from mealie.routes._base.routers import UserAPIRouter

from .food_store import (
    AUTHORITY_RANK,
    NUTRI_KEYS,
    clear_food_nutrition,
    mealdb_image,
    read_food_nutrition,
    write_food_nutrition,
)
from .nutrition import _looks_branded, _lookup_candidates, _select_primary

router = UserAPIRouter(prefix="/fork/foods")


class FoodSearchRequest(BaseModel):
    query: str | None = None  # override; defaults to the food's name


class FoodCandidate(BaseModel):
    source: str
    name: str | None
    kcalPer100: int
    per100: dict[str, float]
    image: str | None = None
    dataType: str | None = None


class FoodSearchResponse(BaseModel):
    food: str
    query: str
    candidates: list[FoodCandidate]
    genericImage: str | None = None  # TheMealDB fallback image for the food itself
    stored: dict | None = None       # current pinned/auto data, for context


class FoodNutritionIn(BaseModel):
    per100: dict[str, float]
    source: str = "manual"  # "usda" | "off" | "nutritionix" | "manual"
    matched_name: str | None = None
    source_detail: str | None = None  # citation, e.g. "USDA FDC #11215" / "Claude estimate"
    authority: str = "manual"  # "official" | "manual" | "estimate"
    image_url: str | None = None
    force: bool = False  # override the estimate-cannot-replace-trusted-data guard


@controller(router)
class ForkFoodDataController(BaseUserController):
    def _get_food(self, food_id: str):
        food = self.repos.ingredient_foods.get_one(food_id)
        if food is None:
            raise HTTPException(404, f"Food {food_id} not found")
        return food

    @router.post("/{food_id}/search", response_model=FoodSearchResponse)
    async def search_food(self, food_id: str, body: FoodSearchRequest) -> FoodSearchResponse:
        """Search USDA + Open Food Facts for nutrition matches for this food,
        ranked by the same scorer the estimator uses, with images."""
        food = self._get_food(food_id)
        query = (body.query or "").strip() or food.name

        async with httpx.AsyncClient() as client:
            candidates, branded = await _lookup_candidates(
                client, query, self.settings.USDA_API_KEY,
                self.settings.NUTRITIONIX_APP_ID, self.settings.NUTRITIONIX_APP_KEY,
            )
            _, _, _, ranked = _select_primary(candidates, branded, query)
            generic_image, *_ = await asyncio.gather(mealdb_image(client, food.name))

        out: list[FoodCandidate] = []
        seen: set[tuple[str, str]] = set()
        for c in ranked:
            key = (c["source"], (c.get("name") or "").lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(FoodCandidate(
                source=c["source"],
                name=c.get("name"),
                kcalPer100=int(round(c["kcal"])),
                per100={k: round(float(c.get(k, 0)), 3) for k in NUTRI_KEYS},
                image=c.get("image") or (generic_image if c["source"] == "usda" else None),
                dataType=c.get("dataType"),
            ))
            if len(out) == 8:
                break

        return FoodSearchResponse(
            food=food.name,
            query=query,
            candidates=out,
            genericImage=generic_image,
            stored=read_food_nutrition(food),
        )

    @router.put("/{food_id}/nutrition")
    async def pin_nutrition(self, food_id: str, body: FoodNutritionIn) -> dict:
        """Pin nutrition data (and optionally an image) to this food. Pinned
        data is used by every future estimate involving the food and is never
        overwritten by automatic matching.

        Guard ("prefer an official one"): a low-confidence `estimate` cannot
        replace an existing trusted (official/manual) pin unless `force=true`."""
        food = self._get_food(food_id)
        authority = body.authority if body.authority in AUTHORITY_RANK else "manual"

        existing = read_food_nutrition(food)
        if (
            existing
            and existing["state"] == "user"
            and not body.force
            and AUTHORITY_RANK[authority] < AUTHORITY_RANK.get(existing["authority"], 2)
        ):
            raise HTTPException(
                409,
                f"Refusing to replace a '{existing['authority']}' value "
                f"({existing.get('name') or 'existing'}) with a lower-trust '{authority}' one. "
                "Pass force=true to override.",
            )

        image_url = body.image_url
        if not image_url:
            async with httpx.AsyncClient() as client:
                image_url = await mealdb_image(client, food.name)
        ok = write_food_nutrition(
            self.repos, food_id, group_id=self.group_id,
            per100=body.per100, source=body.source, name=body.matched_name,
            state="user", authority=authority, source_detail=body.source_detail,
            image_url=image_url,
        )
        if not ok:
            raise HTTPException(500, "Could not save nutrition data")
        return read_food_nutrition(self._get_food(food_id)) or {}

    @router.delete("/{food_id}/nutrition")
    def clear_nutrition(self, food_id: str) -> dict:
        """Remove stored nutrition/image data from this food."""
        self._get_food(food_id)
        clear_food_nutrition(self.repos, food_id, self.group_id)
        return {"cleared": True}
