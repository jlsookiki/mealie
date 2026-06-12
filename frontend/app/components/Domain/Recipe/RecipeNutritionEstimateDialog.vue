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
        <template v-else-if="phase === 'review' && result && effectiveNutrition">
          <div class="d-flex align-baseline ga-1">
            <Transition
              name="est-swap"
              mode="out-in"
            >
              <span
                :key="effectiveNutrition.calories"
                class="estimate-dialog__calories"
              >{{ rounded(effectiveNutrition.calories) }}</span>
            </Transition>
            <span class="estimate-dialog__calories-unit">{{ $t("recipe.calories-suffix") }} · per serving (÷{{ result.servings }})</span>
          </div>
          <div class="d-flex ga-3 mt-1 mb-3">
            <span class="estimate-dialog__macro">{{ rounded(effectiveNutrition.proteinContent) }}g protein</span>
            <span class="estimate-dialog__macro">{{ rounded(effectiveNutrition.carbohydrateContent) }}g carbs</span>
            <span class="estimate-dialog__macro">{{ rounded(effectiveNutrition.fatContent) }}g fat</span>
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
          <v-alert
            v-if="divergentCount > 0"
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ divergentCount }} ingredient(s) where sources disagree (⚠) — double-check those matches.
          </v-alert>

          <div class="estimate-dialog__breakdown">
            <div
              v-for="(b, i) in result.breakdown"
              :key="i"
              class="estimate-dialog__row"
            >
              <div class="estimate-dialog__row-main">
                <span class="estimate-dialog__row-input">
                  {{ b.input }}
                  <v-icon
                    v-if="b.agreement === 'divergent' && selectedIdx(i) === 0"
                    :icon="mdiAlert"
                    size="13"
                    color="warning"
                    class="ml-1"
                  />
                  <v-icon
                    v-else-if="b.agreement === 'pinned'"
                    :icon="mdiPin"
                    size="12"
                    color="primary"
                    class="ml-1"
                    title="Pinned match — set on this ingredient's food"
                  />
                </span>
                <span
                  v-if="rowMatched(b, i) && !sameish(b.input, rowMatched(b, i)!)"
                  class="estimate-dialog__row-matched"
                >→ {{ rowMatched(b, i) }}</span>
                <span
                  v-else-if="!b.source"
                  class="estimate-dialog__row-nomatch"
                >no match</span>
                <!-- Ranked alternatives — tap to swap which match feeds the totals -->
                <div
                  v-if="(b.alternatives?.length ?? 0) > 1"
                  class="estimate-dialog__alts"
                >
                  <button
                    v-for="(alt, ai) in b.alternatives"
                    :key="ai"
                    type="button"
                    class="estimate-dialog__alt"
                    :class="{ 'estimate-dialog__alt--active': selectedIdx(i) === ai }"
                    :aria-pressed="selectedIdx(i) === ai"
                    @click="select(i, ai)"
                  >
                    <span class="estimate-dialog__alt-src">{{ sourceLabel(alt.source) }}</span>
                    <span class="estimate-dialog__alt-name">{{ alt.name }}</span>
                    <span class="estimate-dialog__alt-kcal">{{ alt.kcal }} kcal</span>
                  </button>
                </div>
              </div>
              <Transition
                name="est-swap"
                mode="out-in"
              >
                <span
                  :key="rowKcal(b, i) ?? 'none'"
                  class="estimate-dialog__row-kcal"
                >{{ rowKcal(b, i) != null ? `${rowKcal(b, i)} kcal` : "—" }}</span>
              </Transition>
            </div>
          </div>
          <p class="estimate-dialog__caption mt-2 mb-0">
            Cross-referenced across USDA and Open Food Facts{{ hasNutritionix ? " and Nutritionix" : "" }}. Wrong match?
            Tap an alternative to swap it — the totals update instantly. Still off? Rename the ingredient and
            re-estimate.
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
import { mdiAlert, mdiClose, mdiPin } from "@mdi/js";
import type { Nutrition, Recipe } from "~/lib/api/types/recipe";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import { useUserApi } from "~/composables/api";
import { useIngredientTextParser } from "~/composables/recipes";
import { alert } from "~/composables/use-toast";

type EstimateResult = Awaited<ReturnType<ReturnType<typeof useUserApi>["recipes"]["estimateNutrition"]>>["data"];
type BreakdownRow = NonNullable<EstimateResult>["breakdown"][number];

const open = defineModel<boolean>({ default: false });
const recipe = defineModel<NoUndefinedField<Recipe>>("recipe", { required: true });

const api = useUserApi();
const { ingredientToParserString } = useIngredientTextParser();

const phase = ref<"form" | "loading" | "review">("form");
const servings = ref(4);
const result = ref<EstimateResult>(null);
const errorMessage = ref("");
const saving = ref(false);
const selections = ref<Record<number, number>>({});

watch(open, (v) => {
  if (v) {
    phase.value = "form";
    result.value = null;
    errorMessage.value = "";
    selections.value = {};
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

const SOURCE_LABELS: Record<string, string> = { usda: "USDA", off: "OFF", nutritionix: "NX" };
function sourceLabel(s: string): string {
  return SOURCE_LABELS[s] ?? s;
}

const divergentCount = computed(() =>
  (result.value?.breakdown ?? []).filter(b => b.agreement === "divergent").length,
);

const hasNutritionix = computed(() =>
  (result.value?.breakdown ?? []).some(b => (b.sources ?? []).some(s => s.source === "nutritionix")),
);

// --- alternative swapping ---------------------------------------------------

function selectedIdx(i: number): number {
  return selections.value[i] ?? 0;
}

function select(i: number, ai: number) {
  selections.value = { ...selections.value, [i]: ai };
}

function rowAlt(b: BreakdownRow, i: number) {
  return b.alternatives?.[selectedIdx(i)] ?? null;
}

function rowKcal(b: BreakdownRow, i: number): number | null {
  const alt = rowAlt(b, i);
  return alt ? alt.kcal : b.kcal;
}

function rowMatched(b: BreakdownRow, i: number): string | null {
  const alt = rowAlt(b, i);
  return alt?.name ?? b.matched;
}

// nutrition field → per100 key, mirroring the backend's totals math
const NUTRIENT_FIELDS = [
  ["calories", "kcal"],
  ["proteinContent", "protein"],
  ["fatContent", "fat"],
  ["carbohydrateContent", "carb"],
  ["fiberContent", "fiber"],
  ["sugarContent", "sugar"],
  ["sodiumContent", "sodium_mg"],
  ["cholesterolContent", "chol_mg"],
  ["saturatedFatContent", "sat_fat"],
] as const;

const effectiveNutrition = computed(() => {
  if (!result.value) {
    return null;
  }
  // No swaps → backend totals verbatim (avoids any rounding drift)
  if (!Object.values(selections.value).some(v => v > 0)) {
    return result.value.nutrition;
  }
  const totals: Record<string, number> = {};
  for (const [, key] of NUTRIENT_FIELDS) {
    totals[key] = 0;
  }
  result.value.breakdown.forEach((b, i) => {
    const alt = rowAlt(b, i);
    if (!alt || b.grams == null) {
      return;
    }
    const f = b.grams / 100;
    for (const [, key] of NUTRIENT_FIELDS) {
      totals[key]! += (alt.per100[key] ?? 0) * f;
    }
  });
  const s = result.value.servings || 1;
  const out: Record<string, string> = {};
  for (const [field, key] of NUTRIENT_FIELDS) {
    out[field] = String(Math.round((totals[key]! / s) * 10) / 10);
  }
  return out as NonNullable<EstimateResult>["nutrition"];
});

async function runEstimate() {
  errorMessage.value = "";
  phase.value = "loading";
  try {
    const sourceIngredients = recipe.value.recipeIngredient.filter(i => ingredientToParserString(i));
    const strings = sourceIngredients.map(ingredientToParserString);
    const { data: parsed } = await api.recipes.parseIngredients("nlp", strings);
    // Carry each ingredient's food id through so pinned per-food data is used
    // and fresh matches are cached back onto the food.
    const ingredients = (parsed ?? []).map((p, i) => ({
      ...p.ingredient,
      food_id: sourceIngredients[i]?.food?.id || null,
    }));

    const { data } = await api.recipes.estimateNutrition(ingredients, servings.value || 1);
    if (!data) {
      throw new Error("No response");
    }
    result.value = data;
    selections.value = {};
    phase.value = "review";
  }
  catch (e) {
    console.error(e);
    errorMessage.value = "Couldn't estimate nutrition. Please try again.";
    phase.value = "form";
  }
}

async function save() {
  if (!result.value || !effectiveNutrition.value) {
    return;
  }
  saving.value = true;
  try {
    const nutrition: Nutrition = { ...recipe.value.nutrition, ...effectiveNutrition.value };
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

.estimate-dialog__alts {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 4px;
}

.estimate-dialog__alt {
  display: flex;
  align-items: baseline;
  gap: 6px;
  width: 100%;
  text-align: left;
  font-size: 0.74rem;
  padding: 3px 8px;
  border: 1px solid rgba(var(--v-border-color), 0.12);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition:
    border-color var(--ms-dur-fast, 0.15s) ease,
    background var(--ms-dur-fast, 0.15s) ease;
}

.estimate-dialog__alt:hover {
  border-color: rgba(var(--v-theme-primary), 0.4);
  background: rgba(var(--v-theme-primary), 0.04);
}

.estimate-dialog__alt--active {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.estimate-dialog__alt-src {
  flex: 0 0 auto;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: rgb(var(--v-theme-primary));
}

.estimate-dialog__alt-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.estimate-dialog__alt-kcal {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
  opacity: 0.7;
}

.est-swap-enter-active,
.est-swap-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}

.est-swap-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.est-swap-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .est-swap-enter-active,
  .est-swap-leave-active,
  .estimate-dialog__alt {
    transition: none;
  }
}

.estimate-dialog__row-kcal {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
}
</style>
