<template>
  <v-card
    v-if="hasValues || canEstimate"
    class="nutrition-panel mt-4"
  >
    <v-card-text class="py-4">
      <div class="d-flex align-center mb-1">
        <h3 class="nutrition-panel__title">
          {{ $t("recipe.nutrition") }}
        </h3>
        <v-spacer />
        <span
          v-if="hasValues"
          class="nutrition-panel__caption"
        >{{ servingCaption }}</span>
      </div>

      <!-- Macro-forward display -->
      <template v-if="hasValues">
        <div class="d-flex align-baseline flex-wrap ga-1 mb-3">
          <span
            v-if="recipe.nutrition.calories"
            class="nutrition-panel__calories"
          >{{ round(recipe.nutrition.calories) }}</span>
          <span
            v-if="recipe.nutrition.calories"
            class="nutrition-panel__calories-unit"
          >{{ $t("recipe.calories-suffix") }}</span>
        </div>

        <div
          v-if="macros.length"
          class="nutrition-panel__macros mb-2"
        >
          <div
            v-for="m in macros"
            :key="m.key"
            class="nutrition-panel__macro"
          >
            <div class="nutrition-panel__macro-value">
              {{ m.value }}<span class="nutrition-panel__macro-suffix">g</span>
            </div>
            <div class="nutrition-panel__macro-label">
              {{ m.label }}
            </div>
          </div>
        </div>

        <v-expand-transition>
          <div v-if="detailsOpen">
            <v-divider class="mb-2" />
            <div
              v-for="d in details"
              :key="d.key"
              class="nutrition-panel__row"
            >
              <span>{{ d.label }}</span>
              <span class="nutrition-panel__row-value">{{ d.value }} {{ d.suffix }}</span>
            </div>
          </div>
        </v-expand-transition>
        <v-btn
          v-if="details.length"
          variant="text"
          size="x-small"
          class="px-1 mt-1"
          @click="detailsOpen = !detailsOpen"
        >
          {{ detailsOpen ? "Less" : "More detail" }}
        </v-btn>
      </template>

      <!-- Empty state: one-click estimate -->
      <template v-else>
        <p class="nutrition-panel__hint mb-3">
          No nutrition info yet — estimate it from the ingredients.
        </p>
        <v-btn
          color="primary"
          variant="tonal"
          rounded="lg"
          size="small"
          :loading="estimating"
          @click="estimateAndSave"
        >
          <v-icon
            start
            :icon="mdiCalculatorVariant"
          />
          Estimate nutrition
        </v-btn>
        <p class="nutrition-panel__caption mt-2 mb-0">
          Uses USDA FoodData Central — approximate.
        </p>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { mdiCalculatorVariant } from "@mdi/js";
import type { Nutrition, Recipe } from "~/lib/api/types/recipe";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import { useUserApi } from "~/composables/api";
import { useIngredientTextParser, useNutritionLabels } from "~/composables/recipes";
import { useLoggedInState } from "~/composables/use-logged-in-state";
import { alert } from "~/composables/use-toast";

const recipe = defineModel<NoUndefinedField<Recipe>>({ required: true });

const api = useUserApi();
const { labels } = useNutritionLabels();
const { ingredientToParserString } = useIngredientTextParser();
const { isOwnGroup } = useLoggedInState();

const detailsOpen = ref(false);
const estimating = ref(false);

const MACRO_KEYS = [
  { key: "proteinContent", label: "Protein" },
  { key: "carbohydrateContent", label: "Carbs" },
  { key: "fatContent", label: "Fat" },
] as const;

function present(v: string | null | undefined): boolean {
  return !!v && v.trim() !== "" && Number(v) !== 0;
}

function round(v: string | null | undefined): string {
  const n = Number(v);
  return Number.isFinite(n) ? String(Math.round(n)) : (v ?? "");
}

const hasValues = computed(() => {
  if (!recipe.value.settings?.showNutrition) {
    return false;
  }
  const n = recipe.value.nutrition || {};
  return Object.values(n).some(v => present(v as string));
});

const canEstimate = computed(() => {
  if (hasValues.value || !isOwnGroup.value) {
    return false;
  }
  return (recipe.value.recipeIngredient?.length ?? 0) > 0;
});

const macros = computed(() =>
  MACRO_KEYS
    .filter(m => present(recipe.value.nutrition?.[m.key]))
    .map(m => ({ key: m.key, label: m.label, value: round(recipe.value.nutrition[m.key]) })),
);

const SHOWN_IN_HEADER = new Set(["calories", "proteinContent", "carbohydrateContent", "fatContent"]);

const details = computed(() =>
  Object.entries(labels)
    .filter(([key]) => !SHOWN_IN_HEADER.has(key))
    .filter(([key]) => present((recipe.value.nutrition as Record<string, string | null>)?.[key]))
    .map(([key, label]) => ({
      key,
      label: label.label,
      suffix: label.suffix,
      value: (recipe.value.nutrition as Record<string, string | null>)[key],
    })),
);

const servingCaption = computed(() => {
  const servings = recipe.value.recipeServings || recipe.value.recipeYieldQuantity;
  return servings && servings > 0 ? `per serving · ${servings} servings` : "per recipe";
});

async function estimateAndSave() {
  estimating.value = true;
  try {
    const strings = recipe.value.recipeIngredient.map(ingredientToParserString).filter(Boolean);
    const { data: parsed } = await api.recipes.parseIngredients("nlp", strings);
    const ingredients = (parsed ?? []).map(p => p.ingredient);
    const servings = recipe.value.recipeServings || recipe.value.recipeYieldQuantity || 1;

    const { data: res } = await api.recipes.estimateNutrition(ingredients, servings);
    if (!res) {
      throw new Error("No response");
    }

    const nutrition: Nutrition = { ...recipe.value.nutrition, ...res.nutrition };
    const settings = { ...recipe.value.settings, showNutrition: true };

    const { error } = await api.recipes.patchOne(recipe.value.slug, { nutrition, settings });
    if (error) {
      throw new Error("Save failed");
    }

    recipe.value.nutrition = nutrition;
    recipe.value.settings = settings as NoUndefinedField<Recipe>["settings"];
    alert.success(`Estimated nutrition — matched ${res.matched} of ${res.total} ingredients`);
  }
  catch (e) {
    console.error(e);
    alert.error("Couldn't estimate nutrition. Please try again.");
  }
  finally {
    estimating.value = false;
  }
}
</script>

<style scoped>
.nutrition-panel__title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 600;
}

.nutrition-panel__caption {
  font-size: 0.72rem;
  opacity: 0.55;
}

.nutrition-panel__hint {
  font-size: 0.85rem;
  opacity: 0.7;
}

.nutrition-panel__calories {
  font-family: var(--font-display);
  font-size: 2.2rem;
  font-weight: 600;
  line-height: 1;
}

.nutrition-panel__calories-unit {
  font-size: 0.85rem;
  opacity: 0.6;
}

.nutrition-panel__macros {
  display: flex;
  gap: 8px;
}

.nutrition-panel__macro {
  flex: 1 1 0;
  text-align: center;
  padding: 8px 4px;
  border: 1px solid rgba(var(--v-border-color), 0.1);
  border-radius: var(--ms-radius-lg);
  background: rgba(var(--v-theme-primary), 0.03);
}

.nutrition-panel__macro-value {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.1;
}

.nutrition-panel__macro-suffix {
  font-size: 0.75rem;
  font-weight: 400;
  opacity: 0.6;
}

.nutrition-panel__macro-label {
  font-size: 0.72rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.6;
}

.nutrition-panel__row {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  padding: 2px 0;
}

.nutrition-panel__row-value {
  opacity: 0.75;
  font-variant-numeric: tabular-nums;
}
</style>
