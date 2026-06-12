/**
 * Fork: ingredient → grams estimation, mirroring the backend's conversion in
 * mealie/routes/fork/nutrition.py (_to_grams). Used by the ingredient sheet to
 * show "in this recipe" nutrition values client-side.
 */
import type { RecipeIngredient } from "~/lib/api/types/recipe";

const MASS_G: Record<string, number> = {
  g: 1, gram: 1, grams: 1, gm: 1,
  kg: 1000, kilogram: 1000,
  mg: 0.001,
  oz: 28.3495, ounce: 28.3495, ounces: 28.3495,
  lb: 453.592, lbs: 453.592, pound: 453.592, pounds: 453.592,
};

const VOL_ML: Record<string, number> = {
  "ml": 1, "milliliter": 1, "milliliters": 1,
  "l": 1000, "liter": 1000, "liters": 1000,
  "tsp": 4.92892, "teaspoon": 4.92892, "teaspoons": 4.92892,
  "tbsp": 14.7868, "tablespoon": 14.7868, "tablespoons": 14.7868,
  "cup": 236.588, "cups": 236.588,
  "fl oz": 29.5735, "fluid ounce": 29.5735,
  "pint": 473.176, "pints": 473.176,
  "quart": 946.353, "quarts": 946.353,
  "gallon": 3785.41,
};

const DENSITY: [RegExp, number][] = [
  [/oil|butter|ghee|tahini/, 0.91],
  [/flour|cocoa|powder/, 0.55],
  [/sugar|honey|syrup|molasses/, 0.85],
  [/rice|grain|oat|quinoa|lentil/, 0.85],
  [/milk|cream|yogurt|broth|stock|water|juice|wine|vinegar|sauce/, 1.0],
  [/salt/, 1.2],
];

const COUNT_G: [RegExp, number][] = [
  [/clove/, 3],
  [/egg/, 50],
  [/onion|pepper|apple|potato|orange/, 130],
  [/lemon|lime|tomato|peach|carrot/, 100],
  [/cucumber/, 200],
  [/banana/, 120],
  [/can\b|tin\b/, 400],
  [/packet|package|pouch|jar/, 250],
  [/slice/, 25],
  [/sprig|leaf/, 3],
];

export function ingredientToGrams(ingredient: RecipeIngredient, scale = 1): number {
  const qty = (ingredient.quantity && ingredient.quantity > 0 ? ingredient.quantity : 1) * scale;
  const unit = (ingredient.unit?.name || "").toLowerCase().trim().replace(/\.$/, "");
  const food = (ingredient.food?.name || ingredient.note || "").toLowerCase();

  if (!unit) {
    for (const [pattern, g] of COUNT_G) {
      if (pattern.test(food)) {
        return qty * g;
      }
    }
    return qty * 100;
  }
  if (unit in MASS_G) {
    return qty * MASS_G[unit]!;
  }
  if (unit in VOL_ML) {
    let density = 1.0;
    for (const [pattern, d] of DENSITY) {
      if (pattern.test(food)) {
        density = d;
        break;
      }
    }
    return qty * VOL_ML[unit]! * density;
  }
  for (const [pattern, g] of COUNT_G) {
    if (pattern.test(unit) || pattern.test(food)) {
      return qty * g;
    }
  }
  return qty * 100;
}
