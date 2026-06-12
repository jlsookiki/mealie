<template>
  <v-dialog
    v-model="open"
    max-width="500"
    :fullscreen="$vuetify.display.xs"
  >
    <v-card
      rounded="xl"
      class="ingredient-sheet"
    >
      <!-- Header: image + identity -->
      <div class="d-flex align-center px-5 pt-5 pb-2">
        <div class="ingredient-sheet__img-wrap mr-4">
          <v-img
            v-if="displayImage"
            :src="displayImage"
            cover
            class="ingredient-sheet__img"
          />
          <v-icon
            v-else
            :icon="mdiFoodApple"
            size="30"
            class="ingredient-sheet__img-placeholder"
          />
        </div>
        <div class="flex-grow-1 min-width-0">
          <h2 class="ingredient-sheet__title">
            {{ foodName }}
          </h2>
          <div class="d-flex align-center ga-1 mt-1 flex-wrap">
            <v-chip
              v-if="stored"
              size="x-small"
              variant="tonal"
              :color="stored.state === 'user' ? 'primary' : 'secondary'"
            >
              <v-icon
                start
                size="11"
                :icon="stored.state === 'user' ? mdiPin : mdiAutoFix"
              />
              {{ stored.state === "user" ? "Pinned" : "Auto-matched" }}
            </v-chip>
            <span
              v-if="stored?.name"
              class="ingredient-sheet__matched"
            >{{ stored.name }}</span>
          </div>
        </div>
        <v-btn
          icon
          variant="text"
          @click="open = false"
        >
          <v-icon :icon="mdiClose" />
        </v-btn>
      </div>

      <v-card-text class="px-5 pb-5 pt-1">
        <!-- Nutrition facts -->
        <template v-if="activePer100">
          <div class="d-flex align-center mb-2">
            <span class="ingredient-sheet__section">Nutrition</span>
            <v-spacer />
            <v-btn-toggle
              v-model="factsMode"
              density="compact"
              variant="outlined"
              rounded="lg"
              mandatory
            >
              <v-btn
                size="x-small"
                value="per100"
              >
                per 100g
              </v-btn>
              <v-btn
                size="x-small"
                value="recipe"
                :disabled="!grams"
              >
                this recipe{{ grams ? ` (${Math.round(grams)}g)` : "" }}
              </v-btn>
            </v-btn-toggle>
          </div>

          <div class="d-flex align-baseline ga-1">
            <Transition
              name="est-swap"
              mode="out-in"
            >
              <span
                :key="factsValue('kcal')"
                class="ingredient-sheet__kcal"
              >{{ factsValue("kcal") }}</span>
            </Transition>
            <span class="ingredient-sheet__kcal-unit">{{ $t("recipe.calories-suffix") }}</span>
          </div>
          <div class="ingredient-sheet__macros my-2">
            <div
              v-for="m in MACROS"
              :key="m.key"
              class="ingredient-sheet__macro"
            >
              <div class="ingredient-sheet__macro-value">
                {{ factsValue(m.key) }}<span class="ingredient-sheet__macro-suffix">g</span>
              </div>
              <div class="ingredient-sheet__macro-label">
                {{ m.label }}
              </div>
            </div>
          </div>
          <div
            v-for="d in DETAILS"
            :key="d.key"
            class="ingredient-sheet__row"
          >
            <span>{{ d.label }}</span>
            <span class="ingredient-sheet__row-value">{{ factsValue(d.key) }} {{ d.suffix }}</span>
          </div>
        </template>
        <p
          v-else
          class="ingredient-sheet__empty mb-2"
        >
          No nutrition data for this ingredient yet — search below to match it, or enter values by hand.
        </p>

        <!-- Search & re-match -->
        <div class="d-flex align-center mt-4 mb-2">
          <span class="ingredient-sheet__section">{{ activePer100 ? "Change match" : "Find a match" }}</span>
        </div>
        <v-text-field
          v-model="searchQuery"
          density="compact"
          variant="outlined"
          rounded="lg"
          hide-details
          clearable
          placeholder="Search USDA & Open Food Facts…"
          :loading="searching"
          @keydown.enter.prevent="runSearch"
        >
          <template #append-inner>
            <v-btn
              size="small"
              variant="tonal"
              color="primary"
              rounded="lg"
              :loading="searching"
              @click="runSearch"
            >
              Search
            </v-btn>
          </template>
        </v-text-field>

        <v-expand-transition>
          <div
            v-if="candidates.length"
            class="ingredient-sheet__results mt-2"
          >
            <button
              v-for="(c, i) in candidates"
              :key="i"
              type="button"
              class="ingredient-sheet__result"
              :disabled="pinning"
              @click="pinCandidate(c)"
            >
              <div class="ingredient-sheet__result-img">
                <v-img
                  v-if="c.image"
                  :src="c.image"
                  cover
                  height="34"
                  width="34"
                />
                <v-icon
                  v-else
                  :icon="mdiFoodApple"
                  size="18"
                />
              </div>
              <div class="ingredient-sheet__result-main">
                <span class="ingredient-sheet__result-name">{{ c.name }}</span>
                <span class="ingredient-sheet__result-src">{{ sourceLabel(c.source) }}{{ c.dataType ? ` · ${c.dataType}` : "" }}</span>
              </div>
              <span class="ingredient-sheet__result-kcal">{{ c.kcalPer100 }} kcal/100g</span>
            </button>
          </div>
        </v-expand-transition>
        <p
          v-if="searchedOnce && !searching && !candidates.length"
          class="ingredient-sheet__empty mt-2"
        >
          No matches found — try different words, or enter values manually.
        </p>

        <!-- Manual edit -->
        <div class="d-flex align-center mt-4">
          <v-btn
            variant="text"
            size="small"
            class="px-1"
            @click="editOpen = !editOpen"
          >
            <v-icon
              start
              :icon="editOpen ? mdiChevronUp : mdiPencil"
            />
            {{ editOpen ? "Hide manual edit" : "Edit values manually" }}
          </v-btn>
          <v-spacer />
          <v-btn
            v-if="stored"
            variant="text"
            size="small"
            color="error"
            class="px-1"
            :loading="pinning"
            @click="clearData"
          >
            Clear data
          </v-btn>
        </div>
        <v-expand-transition>
          <div v-if="editOpen">
            <p class="ingredient-sheet__empty mt-1 mb-2">
              Values per 100g.
            </p>
            <div class="ingredient-sheet__edit-grid">
              <v-text-field
                v-for="f in EDIT_FIELDS"
                :key="f.key"
                v-model="editValues[f.key]"
                :label="f.label"
                type="number"
                density="compact"
                variant="outlined"
                rounded="lg"
                hide-details
              />
            </div>
            <v-btn
              color="primary"
              variant="flat"
              rounded="lg"
              size="small"
              class="mt-3"
              :loading="pinning"
              @click="saveManual"
            >
              Save values
            </v-btn>
          </div>
        </v-expand-transition>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
        >
          {{ errorMessage }}
        </v-alert>
        <p class="ingredient-sheet__hint mt-4 mb-0">
          Pinned data applies everywhere this food is used and is never changed by automatic matching.
        </p>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { mdiAutoFix, mdiChevronUp, mdiClose, mdiFoodApple, mdiPencil, mdiPin } from "@mdi/js";
import type { RecipeIngredient } from "~/lib/api/types/recipe";
import type { FoodCandidate, FoodNutritionPer100, FoodNutritionStored } from "~/lib/api/user/recipe-foods";
import { useUserApi } from "~/composables/api";
import { ingredientToGrams } from "~/composables/recipes/use-ingredient-grams";

const open = defineModel<boolean>({ default: false });
const props = defineProps<{
  ingredient: RecipeIngredient | null;
  scale?: number;
}>();
const emit = defineEmits<{ updated: [stored: FoodNutritionStored] }>();

const api = useUserApi();

const stored = ref<FoodNutritionStored | null>(null);
const candidates = ref<FoodCandidate[]>([]);
const genericImage = ref<string | null>(null);
const searchQuery = ref("");
const searching = ref(false);
const searchedOnce = ref(false);
const pinning = ref(false);
const editOpen = ref(false);
const errorMessage = ref("");
const factsMode = ref<"per100" | "recipe">("per100");
const editValues = ref<Record<string, string>>({});

const MACROS = [
  { key: "protein", label: "Protein" },
  { key: "carb", label: "Carbs" },
  { key: "fat", label: "Fat" },
] as const;

const DETAILS = [
  { key: "fiber", label: "Fiber", suffix: "g" },
  { key: "sugar", label: "Sugar", suffix: "g" },
  { key: "sat_fat", label: "Saturated fat", suffix: "g" },
  { key: "sodium_mg", label: "Sodium", suffix: "mg" },
  { key: "chol_mg", label: "Cholesterol", suffix: "mg" },
] as const;

const EDIT_FIELDS = [
  { key: "kcal", label: "Calories" },
  { key: "protein", label: "Protein (g)" },
  { key: "carb", label: "Carbs (g)" },
  { key: "fat", label: "Fat (g)" },
  { key: "fiber", label: "Fiber (g)" },
  { key: "sugar", label: "Sugar (g)" },
  { key: "sat_fat", label: "Sat. fat (g)" },
  { key: "sodium_mg", label: "Sodium (mg)" },
  { key: "chol_mg", label: "Cholest. (mg)" },
] as const;

const foodId = computed(() => props.ingredient?.food?.id || null);
const foodName = computed(() => props.ingredient?.food?.name || props.ingredient?.note || "Ingredient");
const grams = computed(() => (props.ingredient ? ingredientToGrams(props.ingredient, props.scale ?? 1) : 0));

const displayImage = computed(() => stored.value?.image_url || genericImage.value);
const activePer100 = computed(() => stored.value?.per100 ?? null);

function readStoredFromExtras(): FoodNutritionStored | null {
  const extras = (props.ingredient?.food as { extras?: Record<string, string> } | undefined)?.extras;
  if (!extras?.nutri_per100) {
    return null;
  }
  try {
    return {
      per100: JSON.parse(extras.nutri_per100),
      source: (extras.nutri_source as FoodNutritionStored["source"]) || "manual",
      name: extras.nutri_name || null,
      state: (extras.nutri_state as FoodNutritionStored["state"]) || "auto",
      image_url: extras.image_url || null,
    };
  }
  catch {
    return null;
  }
}

watch(open, (v) => {
  if (v) {
    stored.value = readStoredFromExtras();
    candidates.value = [];
    genericImage.value = null;
    searchQuery.value = foodName.value;
    searchedOnce.value = false;
    editOpen.value = false;
    errorMessage.value = "";
    factsMode.value = grams.value ? "recipe" : "per100";
    const p = stored.value?.per100 ?? ({} as Partial<FoodNutritionPer100>);
    editValues.value = Object.fromEntries(EDIT_FIELDS.map(f => [f.key, String(p[f.key as keyof FoodNutritionPer100] ?? 0)]));
  }
});

function factsValue(key: string): string {
  const per100 = activePer100.value as Record<string, number> | null;
  if (!per100) {
    return "0";
  }
  const base = per100[key] ?? 0;
  const value = factsMode.value === "recipe" && grams.value ? base * (grams.value / 100) : base;
  return String(Math.round(value * 10) / 10);
}

const SOURCE_LABELS: Record<string, string> = { usda: "USDA", off: "Open Food Facts", nutritionix: "Nutritionix", manual: "Manual" };
function sourceLabel(s: string): string {
  return SOURCE_LABELS[s] ?? s;
}

async function runSearch() {
  if (!foodId.value) {
    errorMessage.value = "This ingredient isn't linked to a food yet — edit the recipe and pick a food first.";
    return;
  }
  searching.value = true;
  errorMessage.value = "";
  try {
    const { data } = await api.foods.searchNutrition(foodId.value, searchQuery.value);
    if (!data) {
      throw new Error("no data");
    }
    candidates.value = data.candidates;
    genericImage.value = data.genericImage;
    if (data.stored) {
      stored.value = data.stored;
    }
    searchedOnce.value = true;
  }
  catch {
    errorMessage.value = "Search failed — try again.";
  }
  finally {
    searching.value = false;
  }
}

async function pinCandidate(c: FoodCandidate) {
  if (!foodId.value) {
    return;
  }
  pinning.value = true;
  errorMessage.value = "";
  try {
    const { data } = await api.foods.pinNutrition(foodId.value, {
      per100: c.per100,
      source: c.source,
      matched_name: c.name,
      image_url: c.image || genericImage.value,
    });
    if (data) {
      applyStored(data);
    }
  }
  catch {
    errorMessage.value = "Couldn't pin the match — try again.";
  }
  finally {
    pinning.value = false;
  }
}

async function saveManual() {
  if (!foodId.value) {
    return;
  }
  pinning.value = true;
  errorMessage.value = "";
  try {
    const per100 = Object.fromEntries(
      EDIT_FIELDS.map(f => [f.key, Number(editValues.value[f.key]) || 0]),
    ) as unknown as FoodNutritionPer100;
    const { data } = await api.foods.pinNutrition(foodId.value, { per100, source: "manual", matched_name: "Manual entry" });
    if (data) {
      applyStored(data);
      editOpen.value = false;
    }
  }
  catch {
    errorMessage.value = "Couldn't save the values — try again.";
  }
  finally {
    pinning.value = false;
  }
}

async function clearData() {
  if (!foodId.value) {
    return;
  }
  pinning.value = true;
  try {
    await api.foods.clearNutrition(foodId.value);
    stored.value = null;
    syncExtras(null);
  }
  finally {
    pinning.value = false;
  }
}

function applyStored(data: FoodNutritionStored) {
  stored.value = data;
  syncExtras(data);
  emit("updated", data);
}

// Keep the in-memory recipe's food.extras in sync so rows/thumbnails update live.
function syncExtras(data: FoodNutritionStored | null) {
  const food = props.ingredient?.food as { extras?: Record<string, string> } | undefined;
  if (!food) {
    return;
  }
  const extras = { ...(food.extras || {}) };
  if (data) {
    extras.nutri_per100 = JSON.stringify(data.per100);
    extras.nutri_source = data.source;
    extras.nutri_name = data.name || "";
    extras.nutri_state = data.state;
    if (data.image_url) {
      extras.image_url = data.image_url;
    }
  }
  else {
    delete extras.nutri_per100;
    delete extras.nutri_source;
    delete extras.nutri_name;
    delete extras.nutri_state;
    delete extras.image_url;
  }
  food.extras = extras;
}
</script>

<style scoped>
.ingredient-sheet__img-wrap {
  width: 58px;
  height: 58px;
  border-radius: 16px;
  overflow: hidden;
  flex: 0 0 auto;
  background: rgba(var(--v-theme-primary), 0.07);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ingredient-sheet__img {
  width: 100%;
  height: 100%;
}

.ingredient-sheet__img-placeholder {
  opacity: 0.4;
}

.ingredient-sheet__title {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 600;
  line-height: 1.15;
  text-transform: capitalize;
}

.ingredient-sheet__matched {
  font-size: 0.74rem;
  opacity: 0.6;
}

.ingredient-sheet__section {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.55;
}

.ingredient-sheet__kcal {
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 600;
  line-height: 1;
}

.ingredient-sheet__kcal-unit {
  font-size: 0.8rem;
  opacity: 0.6;
}

.ingredient-sheet__macros {
  display: flex;
  gap: 8px;
}

.ingredient-sheet__macro {
  flex: 1 1 0;
  text-align: center;
  padding: 7px 4px;
  border: 1px solid rgba(var(--v-border-color), 0.1);
  border-radius: var(--ms-radius-lg);
  background: rgba(var(--v-theme-primary), 0.03);
}

.ingredient-sheet__macro-value {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 600;
  line-height: 1.1;
}

.ingredient-sheet__macro-suffix {
  font-size: 0.7rem;
  font-weight: 400;
  opacity: 0.6;
}

.ingredient-sheet__macro-label {
  font-size: 0.68rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.6;
}

.ingredient-sheet__row {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  padding: 2px 0;
}

.ingredient-sheet__row-value {
  opacity: 0.75;
  font-variant-numeric: tabular-nums;
}

.ingredient-sheet__empty {
  font-size: 0.82rem;
  opacity: 0.65;
}

.ingredient-sheet__results {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 260px;
  overflow-y: auto;
}

.ingredient-sheet__result {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  padding: 6px 8px;
  border: 1px solid rgba(var(--v-border-color), 0.12);
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  transition:
    border-color var(--ms-dur-fast, 0.15s) ease,
    background var(--ms-dur-fast, 0.15s) ease;
}

.ingredient-sheet__result:hover {
  border-color: rgba(var(--v-theme-primary), 0.4);
  background: rgba(var(--v-theme-primary), 0.04);
}

.ingredient-sheet__result-img {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  overflow: hidden;
  flex: 0 0 auto;
  background: rgba(var(--v-border-color), 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ingredient-sheet__result-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.ingredient-sheet__result-name {
  font-size: 0.84rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ingredient-sheet__result-src {
  font-size: 0.68rem;
  opacity: 0.55;
}

.ingredient-sheet__result-kcal {
  flex: 0 0 auto;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
}

.ingredient-sheet__edit-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.ingredient-sheet__hint {
  font-size: 0.72rem;
  opacity: 0.5;
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
</style>
