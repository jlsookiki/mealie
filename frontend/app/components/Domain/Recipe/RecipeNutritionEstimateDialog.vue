<template>
  <v-dialog
    v-model="open"
    max-width="560"
    :fullscreen="$vuetify.display.xs"
  >
    <v-card
      rounded="xl"
      class="pa-2"
    >
      <div class="d-flex align-center px-5 pt-5 pb-1">
        <h2 class="text-h5">
          Estimate nutrition
        </h2>
        <v-spacer />
        <v-btn
          icon
          variant="text"
          @click="open = false"
        >
          <v-icon :icon="mdiClose" />
        </v-btn>
      </div>

      <v-card-text class="px-5 pt-2">
        <!-- Step 1: servings -->
        <template v-if="phase === 'form'">
          <p class="estimate-dialog__hint mb-4">
            Nutrition is shown per serving, so we need to know how many servings this recipe makes.
          </p>
          <v-number-input
            v-model="servings"
            :min="1"
            :precision="0"
            label="Servings"
            variant="outlined"
            rounded="lg"
            density="comfortable"
            control-variant="split"
            style="max-width: 220px"
          />
          <p class="estimate-dialog__caption mt-2 mb-0">
            Estimates use USDA FoodData Central and Open Food Facts — approximate by nature. You'll see exactly what
            matched before anything is saved.
          </p>
        </template>

        <!-- Step 2: running -->
        <div
          v-else-if="phase === 'loading'"
          class="d-flex align-center py-6"
        >
          <v-progress-circular
            indeterminate
            color="primary"
            size="24"
            width="2"
            class="mr-3"
          />
          <span>Matching {{ recipe.recipeIngredient.length }} ingredients…</span>
        </div>

        <!-- Step 3: review before saving -->
        <template v-else-if="phase === 'review' && result">
          <div class="d-flex align-baseline ga-1">
            <span class="estimate-dialog__calories">{{ rounded(result.nutrition.calories) }}</span>
            <span class="estimate-dialog__calories-unit">{{ $t("recipe.calories-suffix") }} · per serving (÷{{ result.servings }})</span>
          </div>
          <div class="d-flex ga-3 mt-1 mb-3">
            <span class="estimate-dialog__macro">{{ rounded(result.nutrition.proteinContent) }}g protein</span>
            <span class="estimate-dialog__macro">{{ rounded(result.nutrition.carbohydrateContent) }}g carbs</span>
            <span class="estimate-dialog__macro">{{ rounded(result.nutrition.fatContent) }}g fat</span>
          </div>

          <v-alert
            v-if="result.matched < result.total"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ result.total - result.matched }} ingredient(s) had no match and are NOT counted — totals run low.
          </v-alert>

          <div class="estimate-dialog__breakdown">
            <div
              v-for="(b, i) in result.breakdown"
              :key="i"
              class="estimate-dialog__row"
            >
              <div class="estimate-dialog__row-main">
                <span class="estimate-dialog__row-input">{{ b.input }}</span>
                <span
                  v-if="b.matched && !sameish(b.input, b.matched)"
                  class="estimate-dialog__row-matched"
                >→ {{ b.matched }}</span>
                <span
                  v-else-if="!b.source"
                  class="estimate-dialog__row-nomatch"
                >no match</span>
              </div>
              <span class="estimate-dialog__row-kcal">{{ b.kcal != null ? `${b.kcal} kcal` : "—" }}</span>
            </div>
          </div>
          <p class="estimate-dialog__caption mt-2 mb-0">
            Check the matches above — a wrong match skews the totals. Mismatched lines can be fixed by renaming the
            ingredient and re-estimating.
          </p>
        </template>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          density="comfortable"
          class="mt-3"
        >
          {{ errorMessage }}
        </v-alert>
      </v-card-text>

      <v-card-actions class="px-5 pb-4 pt-1">
        <v-btn
          v-if="phase === 'review'"
          variant="text"
          @click="phase = 'form'"
        >
          Back
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="phase === 'form'"
          color="primary"
          variant="flat"
          rounded="lg"
          @click="runEstimate"
        >
          Estimate
        </v-btn>
        <v-btn
          v-else-if="phase === 'review'"
          color="primary"
          variant="flat"
          rounded="lg"
          :loading="saving"
          @click="save"
        >
          Save to recipe
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { mdiClose } from "@mdi/js";
import type { Nutrition, Recipe } from "~/lib/api/types/recipe";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import { useUserApi } from "~/composables/api";
import { useIngredientTextParser } from "~/composables/recipes";
import { alert } from "~/composables/use-toast";

type EstimateResult = Awaited<ReturnType<ReturnType<typeof useUserApi>["recipes"]["estimateNutrition"]>>["data"];

const open = defineModel<boolean>({ default: false });
const recipe = defineModel<NoUndefinedField<Recipe>>("recipe", { required: true });

const api = useUserApi();
const { ingredientToParserString } = useIngredientTextParser();

const phase = ref<"form" | "loading" | "review">("form");
const servings = ref(4);
const result = ref<EstimateResult>(null);
const errorMessage = ref("");
const saving = ref(false);

watch(open, (v) => {
  if (v) {
    phase.value = "form";
    result.value = null;
    errorMessage.value = "";
    servings.value = recipe.value.recipeServings || recipe.value.recipeYieldQuantity || 4;
  }
});

function rounded(v: string | null | undefined): string {
  const n = Number(v);
  return Number.isFinite(n) ? String(Math.round(n)) : (v ?? "");
}

function sameish(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

async function runEstimate() {
  errorMessage.value = "";
  phase.value = "loading";
  try {
    const strings = recipe.value.recipeIngredient.map(ingredientToParserString).filter(Boolean);
    const { data: parsed } = await api.recipes.parseIngredients("nlp", strings);
    const ingredients = (parsed ?? []).map(p => p.ingredient);

    const { data } = await api.recipes.estimateNutrition(ingredients, servings.value || 1);
    if (!data) {
      throw new Error("No response");
    }
    result.value = data;
    phase.value = "review";
  }
  catch (e) {
    console.error(e);
    errorMessage.value = "Couldn't estimate nutrition. Please try again.";
    phase.value = "form";
  }
}

async function save() {
  if (!result.value) {
    return;
  }
  saving.value = true;
  try {
    const nutrition: Nutrition = { ...recipe.value.nutrition, ...result.value.nutrition };
    const settings = { ...recipe.value.settings, showNutrition: true };
    const payload: Partial<Recipe> = { nutrition, settings };
    if (servings.value && servings.value > 0 && servings.value !== recipe.value.recipeServings) {
      payload.recipeServings = servings.value;
    }

    const { error } = await api.recipes.patchOne(recipe.value.slug, payload);
    if (error) {
      throw new Error("Save failed");
    }

    recipe.value.nutrition = nutrition;
    recipe.value.settings = settings as NoUndefinedField<Recipe>["settings"];
    if (payload.recipeServings) {
      recipe.value.recipeServings = payload.recipeServings;
    }
    alert.success("Nutrition saved");
    open.value = false;
  }
  catch (e) {
    console.error(e);
    errorMessage.value = "Couldn't save the estimate. Please try again.";
  }
  finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.estimate-dialog__hint {
  font-size: 0.9rem;
  opacity: 0.75;
}

.estimate-dialog__caption {
  font-size: 0.75rem;
  opacity: 0.55;
}

.estimate-dialog__calories {
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 600;
  line-height: 1;
}

.estimate-dialog__calories-unit {
  font-size: 0.8rem;
  opacity: 0.6;
}

.estimate-dialog__macro {
  font-size: 0.85rem;
  font-weight: 600;
}

.estimate-dialog__breakdown {
  border-top: 1px solid rgba(var(--v-border-color), 0.12);
  max-height: 300px;
  overflow-y: auto;
}

.estimate-dialog__row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.06);
  font-size: 0.82rem;
}

.estimate-dialog__row-main {
  flex: 1 1 auto;
  min-width: 0;
}

.estimate-dialog__row-input {
  font-weight: 500;
}

.estimate-dialog__row-matched {
  display: block;
  opacity: 0.6;
  font-size: 0.76rem;
}

.estimate-dialog__row-nomatch {
  display: block;
  color: rgb(var(--v-theme-warning));
  font-size: 0.76rem;
  font-weight: 600;
}

.estimate-dialog__row-kcal {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
}
</style>
