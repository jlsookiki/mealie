"""
Fork: AI cover-photo generation for recipes without an image.

POST /api/fork/recipes/{slug}/generate-image

Builds an editorial food-photography prompt from the recipe (name + key
ingredients), generates an image with whichever provider is configured, and
saves it through Mealie's normal recipe-image pipeline — so it behaves exactly
like an uploaded photo (same storage, same cache-busting version bump).

Providers (first configured wins, or pass {"provider": ...} to choose):
  gemini        GEMINI_API_KEY        Gemini 2.5 Flash Image ("nano banana")
  pollinations  POLLINATIONS_TOKEN    Flux via pollinations.ai
"""

import base64
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from mealie.routes._base import BaseUserController, controller
from mealie.routes._base.routers import UserAPIRouter
from mealie.services.recipe.recipe_service import RecipeService

router = UserAPIRouter(prefix="/fork/recipes")

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
_POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"


class GenerateImageRequest(BaseModel):
    style: str | None = None     # optional extra style hints from the user
    provider: str | None = None  # force "gemini" | "pollinations"


class GenerateImageResponse(BaseModel):
    image: str        # new image version (cache-bust key)
    provider: str
    prompt: str


def _build_prompt(recipe, style: str | None) -> str:
    """Editorial food photography, matching the app's warm aesthetic."""
    foods = []
    for ing in recipe.recipe_ingredient or []:
        name = getattr(getattr(ing, "food", None), "name", None)
        if name and name.lower() not in ("water", "salt"):
            foods.append(name)
        if len(foods) == 6:
            break
    ingredient_hint = f", featuring {', '.join(foods)}" if foods else ""
    extra = f" {style.strip()}." if style else ""
    return (
        f"Professional overhead food photography of {recipe.name}{ingredient_hint}. "
        "Plated in a rustic ceramic dish on a warm linen-and-wood table, soft natural "
        "window light, shallow depth of field, appetizing editorial cookbook styling, "
        "photorealistic, no text, no hands, no people." + extra
    )


async def _generate_gemini(prompt: str, api_key: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        if resp.status_code != 200:
            detail = resp.json().get("error", {}).get("message", resp.text[:200]) if resp.content else ""
            raise HTTPException(502, f"Gemini error {resp.status_code}: {detail}")
        for part in resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return base64.b64decode(inline["data"]), mime.split("/")[-1]
    raise HTTPException(502, "Gemini returned no image data")


async def _generate_pollinations(prompt: str, token: str) -> tuple[bytes, str]:
    url = _POLLINATIONS_URL.format(prompt=quote(prompt))
    params = {"width": 1024, "height": 768, "model": "flux", "nologo": "true"}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
            raise HTTPException(502, f"Pollinations error {resp.status_code}: {resp.text[:200]}")
        ext = resp.headers["content-type"].split("/")[-1].split(";")[0] or "jpeg"
        return resp.content, ext


@controller(router)
class ForkRecipeImageController(BaseUserController):
    @router.post("/{slug}/generate-image", response_model=GenerateImageResponse)
    async def generate_image(self, slug: str, body: GenerateImageRequest) -> GenerateImageResponse:
        """Generate an AI cover photo for the recipe and set it as the recipe
        image. Intended for recipes without a photo; calling it on a recipe
        with one replaces it (the UI confirms first)."""
        gemini_key = getattr(self.settings, "GEMINI_API_KEY", "")
        pollinations_token = getattr(self.settings, "POLLINATIONS_TOKEN", "")

        provider = body.provider or ("gemini" if gemini_key else "pollinations" if pollinations_token else None)
        if provider == "gemini" and not gemini_key:
            provider = None
        if provider == "pollinations" and not pollinations_token:
            provider = None
        if provider is None:
            raise HTTPException(
                503,
                "No image-generation provider configured. Set GEMINI_API_KEY or POLLINATIONS_TOKEN.",
            )

        service = RecipeService(self.repos, self.user, self.household, translator=self.translator)
        recipe = service.get_one(slug)
        if recipe is None:
            raise HTTPException(404, f"Recipe '{slug}' not found")

        prompt = _build_prompt(recipe, body.style)
        if provider == "gemini":
            image_bytes, ext = await _generate_gemini(prompt, gemini_key)
        else:
            image_bytes, ext = await _generate_pollinations(prompt, pollinations_token)

        new_version = service.update_recipe_image(slug, image_bytes, ext)
        return GenerateImageResponse(image=str(new_version), provider=provider, prompt=prompt)
