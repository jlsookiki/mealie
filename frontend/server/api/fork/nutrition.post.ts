import { analyzeNutrition, type AnalyzeIngredient } from "~~/server/utils/nutrition";

// POST /api/fork/nutrition — { ingredients: AnalyzeIngredient[], servings: number }
// Returns per-serving Mealie nutrition + a per-ingredient breakdown.
export default defineEventHandler(async (event) => {
  const body = await readBody<{ ingredients?: AnalyzeIngredient[]; servings?: number }>(event);
  const apiKey = (useRuntimeConfig().usdaApiKey as string) || "DEMO_KEY";

  const ingredients = Array.isArray(body?.ingredients) ? body.ingredients : [];
  const servings = Number(body?.servings) || 1;

  if (!ingredients.length) {
    return { nutrition: {}, breakdown: [], servings, matched: 0, total: 0 };
  }

  return await analyzeNutrition(ingredients, servings, apiKey);
});
