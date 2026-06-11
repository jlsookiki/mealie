from fastapi import APIRouter

from . import nutrition

router = APIRouter()
router.include_router(nutrition.router, tags=["Fork: Nutrition"])
