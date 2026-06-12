from fastapi import APIRouter

from . import food_data, nutrition, oauth, recipe_image

router = APIRouter()
router.include_router(nutrition.router, tags=["Fork: Nutrition"])
router.include_router(food_data.router, tags=["Fork: Food Data"])
router.include_router(recipe_image.router, tags=["Fork: Recipe Image"])
router.include_router(oauth.public_router, tags=["Fork: OAuth"])
router.include_router(oauth.user_router, tags=["Fork: OAuth"])
