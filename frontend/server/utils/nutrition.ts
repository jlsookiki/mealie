// Nutrition analysis: turn parsed ingredients into per-serving nutrition by
// converting each to grams and looking up USDA FoodData Central (generic) with
// an Open Food Facts fallback (branded/packaged). All estimates are approximate
// — volume→gram uses density heuristics, counts use typical item weights.

export interface AnalyzeIngredient {
  quantity?: number | null;
  unit?: { name?: string | null } | string | null;
  food?: { name?: string | null } | string | null;
  note?: string | null;
}

interface Per100 {
  kcal: number;
  protein: number;
  fat: number;
  carb: number;
  fiber: number;
  sugar: number;
  sodiumMg: number;
  cholMg: number;
  satFat: number;
}

export interface IngredientBreakdown {
  input: string;
  grams: number | null;
  matched: string | null;
  source: "usda" | "off" | null;
  kcal: number | null;
}

const MASS_G: Record<string, number> = {
  g: 1, gram: 1, grams: 1, gm: 1, kg: 1000, kilogram: 1000, mg: 0.001,
  oz: 28.3495, ounce: 28.3495, ounces: 28.3495,
  lb: 453.592, lbs: 453.592, pound: 453.592, pounds: 453.592,
};

const VOL_ML: Record<string, number> = {
  ml: 1, milliliter: 1, milliliters: 1, l: 1000, liter: 1000, liters: 1000,
  tsp: 4.92892, teaspoon: 4.92892, teaspoons: 4.92892,
  tbsp: 14.7868, tablespoon: 14.7868, tablespoons: 14.7868,
  cup: 236.588, cups: 236.588,
  "fl oz": 29.5735, "fluid ounce": 29.5735,
  pint: 473.176, pints: 473.176, quart: 946.353, quarts: 946.353, gallon: 3785.41,
};

// Approximate density (g/ml) by food keyword, for volume→gram conversion.
const DENSITY: [RegExp, number][] = [
  [/oil|butter|ghee|tahini/, 0.91],
  [/flour|cocoa|powder/, 0.55],
  [/sugar|honey|syrup|molasses/, 0.85],
  [/rice|grain|oat|quinoa|lentil/, 0.85],
  [/milk|cream|yogurt|broth|stock|water|juice|wine|vinegar|sauce/, 1.0],
  [/salt/, 1.2],
];

// Typical weight (g) for counted items lacking a unit, by keyword.
const COUNT_G: [RegExp, number][] = [
  [/clove/, 3], [/egg/, 50], [/onion|pepper|apple|potato|orange/, 130],
  [/lemon|lime|tomato|peach|carrot/, 100], [/cucumber/, 200], [/banana/, 120],
  [/can\b|tin\b/, 400], [/packet|package|pouch|jar/, 250], [/slice/, 25], [/sprig|leaf/, 3],
];

function norm(s: unknown): string {
  return (s ?? "").toString().toLowerCase().trim().replace(/\.$/, "");
}

export function toGrams(qty: number | null | undefined, unitName: string, foodName: string): number {
  const q = qty && qty > 0 ? qty : 1;
  const u = norm(unitName);
  const food = norm(foodName);

  if (!u) {
    for (const [re, g] of COUNT_G) {
      if (re.test(food)) {
        return q * g;
      }
    }
    return q * 100;
  }
  if (u in MASS_G) {
    return q * MASS_G[u];
  }
  if (u in VOL_ML) {
    let density = 1;
    for (const [re, d] of DENSITY) {
      if (re.test(food)) {
        density = d;
        break;
      }
    }
    return q * VOL_ML[u] * density;
  }
  for (const [re, g] of COUNT_G) {
    if (re.test(u) || re.test(food)) {
      return q * g;
    }
  }
  return q * 100;
}

async function lookupUSDA(query: string, apiKey: string): Promise<Per100 | null> {
  try {
    const res = await $fetch<any>("https://api.nal.usda.gov/fdc/v1/foods/search", {
      query: { query, pageSize: 1, dataType: "Foundation,SR Legacy", api_key: apiKey },
    });
    const food = res?.foods?.[0];
    if (!food) {
      return null;
    }
    const byNum: Record<string, number> = {};
    for (const n of food.foodNutrients ?? []) {
      if (n.nutrientNumber != null) {
        byNum[n.nutrientNumber] = n.value ?? 0;
      }
    }
    return {
      kcal: byNum["208"] ?? 0,
      protein: byNum["203"] ?? 0,
      fat: byNum["204"] ?? 0,
      carb: byNum["205"] ?? 0,
      fiber: byNum["291"] ?? 0,
      sugar: byNum["269"] ?? byNum["2000"] ?? 0,
      sodiumMg: byNum["307"] ?? 0,
      cholMg: byNum["601"] ?? 0,
      satFat: byNum["606"] ?? 0,
    };
  }
  catch {
    return null;
  }
}

async function offSearch(term: string): Promise<any | null> {
  const res = await $fetch<any>("https://world.openfoodfacts.org/cgi/search.pl", {
    query: { search_terms: term, search_simple: 1, action: "process", json: 1, page_size: 1 },
    headers: { "User-Agent": "MealieFork/1.0 (self-hosted)" },
  });
  return res?.products?.[0]?.nutriments ?? null;
}

async function lookupOFF(query: string): Promise<Per100 | null> {
  try {
    let n = await offSearch(query);
    // Long branded names often return nothing; retry with the first few words.
    if (!n && query.split(/\s+/).length > 4) {
      n = await offSearch(query.split(/\s+/).slice(0, 4).join(" "));
    }
    if (!n) {
      return null;
    }
    return {
      kcal: n["energy-kcal_100g"] ?? 0,
      protein: n.proteins_100g ?? 0,
      fat: n.fat_100g ?? 0,
      carb: n.carbohydrates_100g ?? 0,
      fiber: n.fiber_100g ?? 0,
      sugar: n.sugars_100g ?? 0,
      sodiumMg: (n.sodium_100g ?? 0) * 1000,
      cholMg: (n.cholesterol_100g ?? 0) * 1000,
      satFat: n["saturated-fat_100g"] ?? 0,
    };
  }
  catch {
    return null;
  }
}

function round(n: number): string {
  return (Math.round(n * 10) / 10).toString();
}

// Packaged/branded items (a parenthetical size, or a multi-word proper name)
// are better served by Open Food Facts than USDA's fuzzy generic search.
function looksBranded(q: string): boolean {
  if (/\([^)]*\b(oz|g|ml|gram|grams|each|pack|packet|count|ct)\b[^)]*\)/i.test(q)) {
    return true;
  }
  return (q.match(/\b[A-Z][a-z]+/g) || []).length >= 2;
}

// Reduce an ingredient phrase to a searchable core: drop parentheticals,
// trailing prep notes after a comma, and stray sizes.
function cleanQuery(q: string): string {
  return q
    .replace(/\([^)]*\)/g, "")
    .split(",")[0]
    .replace(/\b\d+(\.\d+)?\s*(oz|g|ml|lb|kg|pound|ounce|gram)s?\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function lookupFood(query: string, apiKey: string): Promise<{ per100: Per100; source: "usda" | "off" } | null> {
  const branded = looksBranded(query);
  const term = cleanQuery(query) || query;
  const primary = branded ? "off" : "usda";
  const first = primary === "off" ? await lookupOFF(term) : await lookupUSDA(term, apiKey);
  if (first && first.kcal) {
    return { per100: first, source: primary };
  }
  const second = primary === "off" ? await lookupUSDA(term, apiKey) : await lookupOFF(term);
  if (second && second.kcal) {
    return { per100: second, source: primary === "off" ? "usda" : "off" };
  }
  return null;
}

export async function analyzeNutrition(ingredients: AnalyzeIngredient[], servings: number, apiKey: string) {
  const totals: Per100 = { kcal: 0, protein: 0, fat: 0, carb: 0, fiber: 0, sugar: 0, sodiumMg: 0, cholMg: 0, satFat: 0 };
  const breakdown: IngredientBreakdown[] = [];

  await Promise.all(ingredients.map(async (ing) => {
    const foodName = typeof ing.food === "string" ? ing.food : (ing.food?.name ?? "");
    const unitName = typeof ing.unit === "string" ? ing.unit : (ing.unit?.name ?? "");
    const query = (foodName || ing.note || "").trim();
    if (!query) {
      breakdown.push({ input: ing.note ?? "", grams: null, matched: null, source: null, kcal: null });
      return;
    }

    const grams = toGrams(ing.quantity, unitName, foodName || ing.note || "");

    const hit = await lookupFood(query, apiKey);
    if (!hit) {
      breakdown.push({ input: query, grams: Math.round(grams), matched: null, source: null, kcal: null });
      return;
    }
    const { per100, source } = hit;

    const f = grams / 100;
    totals.kcal += per100.kcal * f;
    totals.protein += per100.protein * f;
    totals.fat += per100.fat * f;
    totals.carb += per100.carb * f;
    totals.fiber += per100.fiber * f;
    totals.sugar += per100.sugar * f;
    totals.sodiumMg += per100.sodiumMg * f;
    totals.cholMg += per100.cholMg * f;
    totals.satFat += per100.satFat * f;

    breakdown.push({ input: query, grams: Math.round(grams), matched: query, source, kcal: Math.round(per100.kcal * f) });
  }));

  const s = servings && servings > 0 ? servings : 1;
  const nutrition = {
    calories: round(totals.kcal / s),
    proteinContent: round(totals.protein / s),
    fatContent: round(totals.fat / s),
    carbohydrateContent: round(totals.carb / s),
    fiberContent: round(totals.fiber / s),
    sugarContent: round(totals.sugar / s),
    sodiumContent: round(totals.sodiumMg / s),
    cholesterolContent: round(totals.cholMg / s),
    saturatedFatContent: round(totals.satFat / s),
  };

  const matched = breakdown.filter(b => b.source).length;
  return { nutrition, breakdown, servings: s, matched, total: ingredients.length };
}
