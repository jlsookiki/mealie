import { BaseCRUDAPI } from "../base/base-clients";
import type { CreateIngredientFood, IngredientFood } from "~/lib/api/types/recipe";

const prefix = "/api";

const routes = {
  food: `${prefix}/foods`,
  foodsFood: (tag: string) => `${prefix}/foods/${tag}`,
  merge: `${prefix}/foods/merge`,
};

// Fork: persistent per-food nutrition + image data (Food.extras)
export interface FoodNutritionPer100 {
  kcal: number;
  protein: number;
  fat: number;
  carb: number;
  fiber: number;
  sugar: number;
  sodium_mg: number;
  chol_mg: number;
  sat_fat: number;
}

export type FoodAuthority = "official" | "manual" | "estimate";

export interface FoodNutritionStored {
  per100: FoodNutritionPer100;
  source: "usda" | "off" | "nutritionix" | "manual" | "claude";
  sourceDetail: string | null;
  authority: FoodAuthority;
  name: string | null;
  state: "user" | "auto";
  image_url: string | null;
}

export interface FoodCandidate {
  source: "usda" | "off" | "nutritionix";
  name: string | null;
  kcalPer100: number;
  per100: FoodNutritionPer100;
  image: string | null;
  dataType: string | null;
}

export class FoodAPI extends BaseCRUDAPI<CreateIngredientFood, IngredientFood> {
  baseRoute: string = routes.food;
  itemRoute = routes.foodsFood;

  merge(fromId: string, toId: string) {
    return this.requests.put<IngredientFood>(routes.merge, { fromFood: fromId, toFood: toId });
  }

  searchNutrition(foodId: string, query = "") {
    return this.requests.post<{
      food: string;
      query: string;
      candidates: FoodCandidate[];
      genericImage: string | null;
      stored: FoodNutritionStored | null;
    }>(`${prefix}/fork/foods/${foodId}/search`, { query: query || null });
  }

  pinNutrition(foodId: string, payload: {
    per100: FoodNutritionPer100;
    source: string;
    matched_name?: string | null;
    source_detail?: string | null;
    authority?: FoodAuthority;
    image_url?: string | null;
    force?: boolean;
  }) {
    return this.requests.put<FoodNutritionStored>(`${prefix}/fork/foods/${foodId}/nutrition`, payload);
  }

  clearNutrition(foodId: string) {
    return this.requests.delete<{ cleared: boolean }>(`${prefix}/fork/foods/${foodId}/nutrition`);
  }
}
