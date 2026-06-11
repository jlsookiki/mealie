<template>
  <v-card class="mt-2">
    <v-card-text class="py-3">
      <div class="d-flex align-center flex-wrap ga-2">
        <v-btn
          color="primary"
          variant="tonal"
          rounded="lg"
          :loading="loading"
          :disabled="!hasIngredients"
          @click="calculate"
        >
          <v-icon
            start
            :icon="mdiCalculatorVariant"
          />
          Estimate from ingredients
        </v-btn>
        <span
          v-if="result"
          class="text-caption nutri-muted"
        >
          Matched {{ result.matched }}/{{ result.total }} · per serving (÷{{ result.servings }})
        </span>
      </div>

      <p class="text-caption mt-2 mb-0 nutri-muted">
        Estimated from USDA FoodData Central + Open Food Facts — approximate, review before relying on it.
      </p>

      <v-expand-transition>
        <div
          v-if="result"
          class="mt-3 nutri-breakdown"
        >
          <div
            v-for="(b, i) in result.breakdown"
            :key="i"
            class="nutri-row"
          >
            <span class="nutri-row__name">{{ b.input }}</span>
            <span class="nutri-row__grams">{{ b.grams != null ? `${b.grams} g` : "—" }}</span>
            <span class="nutri-row__kcal">{{ b.kcal != null ? `${b.kcal} kcal` : "no match" }}</span>
            <v-chip
              v-if="b.source"
              size="x-small"
              variant="tonal"
              :color="b.source === 'off' ? 'accent' : 'secondary'"
            >
              {{ b.source === "off" ? "OFF" : "USDA" }}
            </v-chip>
            <span
              v-else
              class="nutri-row__nomatch"
            >·</span>
          </div>
        </div>
      </v-expand-transition>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { mdiCalculatorVariant } from "@mdi/js";
import type { Nutrition, Recipe } from "~/lib/api/types/recipe";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import { useUserApi } from "~/composables/api";
import { useIngredientTextParser } from "~/composables/recipes";
import { alert } from "~/composables/use-toast";

interface Breakdown {
  input: string;
  grams: number | null;
  kcal: number | null;
  source: "usda" | "off" | null;
}
interface AnalyzeResult {
  nutrition: Partial<Nutrition>;
  breakdown: Breakdown[];
  servings: number;
  matched: number;
  total: number;
}

const props = defineProps<{ recipe: NoUndefinedField<Recipe> }>();
const nutrition = defineModel<Nutrition>({ required: true });

const api = useUserApi();
const { ingredientToParserString } = useIngredientTextParser();

const loading = ref(false);
const result = ref<AnalyzeResult | null>(null);

const hasIngredients = computed(() => (props.recipe.recipeIngredient?.length ?? 0) > 0);

async function calculate() {
  if (!hasIngredients.value) {
    return;
  }
  loading.value = true;
  try {
    const strings = props.recipe.recipeIngredient.map(ingredientToParserString).filter(Boolean);
    const { data: parsed } = await api.recipes.parseIngredients("nlp", strings);
    const ingredients = (parsed ?? []).map(p => p.ingredient);
    const servings = props.recipe.recipeServings || props.recipe.recipeYieldQuantity || 1;

    const res = await $fetch<AnalyzeResult>("/api/fork/nutrition", {
      method: "POST",
      body: { ingredients, servings },
    });

    result.value = res;
    nutrition.value = { ...nutrition.value, ...res.nutrition };
    // Surface the nutrition card now that we've populated it.
    if (props.recipe.settings) {
      props.recipe.settings.showNutrition = true;
    }
    alert.success(`Estimated nutrition — matched ${res.matched} of ${res.total} ingredients`);
  }
  catch (e) {
    console.error(e);
    alert.error("Couldn't estimate nutrition. Please try again.");
  }
  finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.nutri-muted {
  opacity: 0.6;
}
.nutri-breakdown {
  border-top: 1px solid rgba(var(--v-border-color), 0.12);
}
.nutri-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 0.8rem;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.06);
}
.nutri-row__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nutri-row__grams,
.nutri-row__kcal {
  flex: 0 0 auto;
  opacity: 0.7;
  font-variant-numeric: tabular-nums;
}
.nutri-row__kcal {
  min-width: 64px;
  text-align: right;
}
.nutri-row__nomatch {
  opacity: 0.4;
}
</style>
