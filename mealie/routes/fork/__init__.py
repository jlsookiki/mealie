from fastapi import APIRouter

from . import nutrition, oauth

router = APIRouter()
router.include_router(nutrition.router, tags=["Fork: Nutrition"])
router.include_router(oauth.public_router, tags=["Fork: OAuth"])
router.include_router(oauth.user_router, tags=["Fork: OAuth"])
