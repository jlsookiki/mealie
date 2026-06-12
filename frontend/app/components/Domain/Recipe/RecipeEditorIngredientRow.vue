<template>
  <div class="editor-row ingredient-row">
    <!-- Optional section title -->
    <v-text-field
      v-if="model.title || state.showTitle"
      v-model="model.title"
      density="compact"
      variant="underlined"
      hide-details
      class="ingredient-row__section mb-2"
      :placeholder="$t('recipe.section-title')"
    />

    <div class="ingredient-row__line d-flex align-center">
      <v-icon
        class="handle ingredient-row__handle"
        :icon="mdiDragVertical"
      />

      <v-number-input
        v-model="model.quantity"
        class="ingredient-row__qty"
        variant="plain"
        :precision="null"
        :min="0"
        hide-details
        control-variant="hidden"
        density="compact"
        :placeholder="$t('recipe.quantity')"
        @keypress="quantityFilter"
      />

      <v-autocomplete
        ref="unitAutocomplete"
        v-model="model.unit"
        v-model:search="unitSearch"
        class="ingredient-row__unit"
        auto-select-first
        hide-details
        density="compact"
        variant="plain"
        return-object
        :items="filteredUnits"
        :custom-filter="() => true"
        item-title="name"
        :placeholder="$t('recipe.choose-unit')"
        clearable
        :menu-props="{ maxHeight: '250px' }"
        @keyup.enter="handleUnitEnter"
      >
        <template #no-data>
          <div class="caption text-center pb-2">
            {{ $t("recipe.press-enter-to-create") }}
          </div>
        </template>
        <template #append-item>
          <div
            v-if="showCreateUnit"
            class="px-2"
          >
            <BaseButton
              block
              size="small"
              @click="createAssignUnit()"
            />
          </div>
        </template>
      </v-autocomplete>

      <!-- Food / linked-recipe -->
      <v-autocomplete
        v-if="!state.isRecipe"
        ref="foodAutocomplete"
        v-model="model.food"
        v-model:search="foodSearch"
        class="ingredient-row__food"
        auto-select-first
        hide-details
        density="compact"
        variant="plain"
        return-object
        :items="filteredFoods"
        :custom-filter="() => true"
        item-title="name"
        :placeholder="$t('recipe.choose-food')"
        clearable
        :menu-props="{ maxHeight: '250px' }"
        @keyup.enter="handleFoodEnter"
      >
        <template #no-data>
          <div class="caption text-center pb-2">
            {{ $t("recipe.press-enter-to-create") }}
          </div>
        </template>
        <template #append-item>
          <div
            v-if="showCreateFood"
            class="px-2"
          >
            <BaseButton
              block
              size="small"
              @click="createAssignFood()"
            />
          </div>
        </template>
      </v-autocomplete>
      <v-autocomplete
        v-else
        v-model="model.referencedRecipe"
        v-model:search="search.query.value"
        class="ingredient-row__food"
        auto-select-first
        hide-details
        density="compact"
        variant="plain"
        return-object
        :items="search.data.value || []"
        item-title="name"
        :placeholder="$t('recipe.choose-recipe')"
        clearable
        @click="search.trigger()"
        @focus="search.trigger()"
      />

      <v-text-field
        ref="noteField"
        v-model="model.note"
        class="ingredient-row__note"
        hide-details
        density="compact"
        variant="plain"
        :placeholder="$t('recipe.notes')"
        @keydown.enter.prevent="$emit('note-enter')"
      />

      <div class="ingredient-row__actions d-flex align-center">
        <v-btn
          v-if="model.food?.id"
          icon
          size="x-small"
          variant="text"
          :title="`Nutrition & image for ${model.food?.name}`"
          @click="$emit('food-info')"
        >
          <v-icon :icon="mdiFoodApple" />
        </v-btn>
        <v-btn
          icon
          size="x-small"
          variant="text"
          @click="$emit('delete')"
        >
          <v-icon :icon="mdiDeleteOutline" />
        </v-btn>
        <v-menu>
          <template #activator="{ props: menuProps }">
            <v-btn
              icon
              size="x-small"
              variant="text"
              v-bind="menuProps"
            >
              <v-icon :icon="mdiDotsVertical" />
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item @click="toggleTitle">
              <v-list-item-title>{{ $t("recipe.toggle-section") }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="toggleIsRecipe">
              <v-list-item-title>{{ $t("recipe.toggle-recipe") }}</v-list-item-title>
            </v-list-item>
            <v-divider class="my-1" />
            <v-list-item @click="$emit('insert-above')">
              <v-list-item-title>{{ $t("recipe.insert-above") }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="$emit('insert-below')">
              <v-list-item-title>{{ $t("recipe.insert-below") }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { mdiDeleteOutline, mdiDotsVertical, mdiDragVertical, mdiFoodApple } from "@mdi/js";
import { useFoodStore, useFoodData, useUnitStore, useUnitData } from "~/composables/store";
import { useSearch } from "~/composables/use-search";
import type { RecipeIngredient } from "~/lib/api/types/recipe";
import { usePublicExploreApi, useUserApi } from "~/composables/api";
import { useRecipeSearch } from "~/composables/recipes/use-recipe-search";
import { useLoggedInState } from "~/composables/use-logged-in-state";

const model = defineModel<RecipeIngredient>({ required: true });

const props = defineProps({
  isRecipe: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["delete", "insert-above", "insert-below", "note-enter", "food-info"]);

const state = reactive({
  showTitle: false,
  isRecipe: props.isRecipe,
});

// Foods
const foodStore = useFoodStore();
const foodData = useFoodData();
const foodAutocomplete = ref<HTMLInputElement>();
const { search: foodSearch, filtered: filteredFoods } = useSearch(foodStore.store);

const showCreateFood = computed(() =>
  !!foodSearch.value
  && !filteredFoods.value.some((f: any) => (f.name ?? "").toLowerCase() === foodSearch.value.toLowerCase()),
);

async function createAssignFood() {
  foodData.data.name = foodSearch.value;
  model.value.food = (await foodStore.actions.createOne(foodData.data)) || undefined;
  foodData.reset();
  foodAutocomplete.value?.blur();
}

// Units
const unitStore = useUnitStore();
const unitsData = useUnitData();
const unitAutocomplete = ref<HTMLInputElement>();
const { search: unitSearch, filtered: filteredUnits } = useSearch(unitStore.store);

const showCreateUnit = computed(() =>
  !!unitSearch.value
  && !filteredUnits.value.some((u: any) => (u.name ?? "").toLowerCase() === unitSearch.value.toLowerCase()),
);

async function createAssignUnit() {
  unitsData.data.name = unitSearch.value;
  model.value.unit = (await unitStore.actions.createOne(unitsData.data)) || undefined;
  unitsData.reset();
  unitAutocomplete.value?.blur();
}

// Linked recipes
const route = useRoute();
const auth = useMealieAuth();
const groupSlug = computed(() => (route.params.groupSlug as string) || auth.user.value?.groupSlug || "");
const { isOwnGroup } = useLoggedInState();
const api = isOwnGroup.value ? useUserApi() : usePublicExploreApi(groupSlug.value).explore;
const search = useRecipeSearch(api);

function toggleTitle() {
  if (state.showTitle) {
    model.value.title = "";
  }
  state.showTitle = !state.showTitle;
}

function toggleIsRecipe() {
  if (state.isRecipe) {
    model.value.referencedRecipe = undefined;
  }
  else {
    model.value.unit = undefined;
    model.value.food = undefined;
  }
  state.isRecipe = !state.isRecipe;
}

function handleUnitEnter() {
  if (model.value.unit === undefined || model.value.unit === null || !model.value.unit.name.includes(unitSearch.value)) {
    createAssignUnit();
  }
}

function handleFoodEnter() {
  if (model.value.food === undefined || model.value.food === null || !model.value.food.name.includes(foodSearch.value)) {
    createAssignFood();
  }
}

function quantityFilter(e: KeyboardEvent) {
  if (e.key === "-" || e.key === "+" || e.key === "e") {
    e.preventDefault();
  }
}

const noteField = ref<HTMLInputElement>();

defineExpose({
  focusNote: () => noteField.value?.focus(),
});
</script>

<style scoped>
.ingredient-row {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), 0.1);
  border-radius: var(--ms-radius-lg);
  padding: 4px 10px;
  margin-bottom: 8px;
  transition:
    box-shadow var(--ms-dur-fast) var(--ms-ease),
    border-color var(--ms-dur-fast) var(--ms-ease);
}

.ingredient-row:hover,
.ingredient-row:focus-within {
  box-shadow: var(--ms-shadow-sm);
  border-color: rgba(var(--v-border-color), 0.2);
}

.ingredient-row__line {
  gap: 8px;
  flex-wrap: wrap;
}

.ingredient-row__handle {
  cursor: grab;
  flex: 0 0 auto;
}

.ingredient-row__qty {
  flex: 0 0 76px;
  min-width: 76px;
}

.ingredient-row__unit {
  flex: 1 1 110px;
  min-width: 110px;
}

.ingredient-row__food {
  flex: 1.4 1 150px;
  min-width: 150px;
}

.ingredient-row__note {
  flex: 2 1 180px;
  min-width: 150px;
}

.ingredient-row__section {
  max-width: 420px;
}

.ingredient-row__section :deep(input) {
  font-family: var(--font-display);
  font-weight: 600;
}

.ingredient-row__actions {
  flex: 0 0 auto;
  opacity: 0.25;
  transition: opacity var(--ms-dur-fast) var(--ms-ease);
}

.ingredient-row:hover .ingredient-row__actions,
.ingredient-row:focus-within .ingredient-row__actions {
  opacity: 1;
}

/* Compact the plain-variant field paddings for a tight single line */
.ingredient-row :deep(.v-field--variant-plain .v-field__input) {
  padding-top: 6px;
  padding-bottom: 6px;
}

@media (max-width: 700px) {
  .ingredient-row__note {
    flex-basis: 100%;
  }
}
</style>
