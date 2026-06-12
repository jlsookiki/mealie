<template>
  <div v-if="value && value.length > 0">
    <div
      v-if="!isCookMode"
      class="d-flex justify-start"
    >
      <h2 class="mt-1 text-h5 font-weight-medium opacity-80">
        {{ $t("recipe.ingredients") }}
      </h2>
      <AppButtonCopy
        btn-class="ml-auto"
        :copy-text="ingredientCopyText"
      />
    </div>
    <div>
      <div
        v-for="(ingredient, index) in value"
        :key="'ingredient' + index"
      >
        <h3
          v-if="showTitleEditor[index]"
          class="mt-4 mb-0"
        >
          {{ ingredient.title }}
        </h3>
        <v-divider v-if="showTitleEditor[index]" class="my-2" />
        <v-list-item
          density="compact"
          class="pa-0"
          @click.stop="toggleChecked(index)"
        >
          <template #prepend>
            <v-checkbox
              v-model="checked[index]"
              hide-details
              class="pt-0 my-auto py-auto"
              color="secondary"
              density="comfortable"
            />
            <button
              v-if="ingredient.food?.id"
              type="button"
              class="ingredient-thumb mr-3"
              :title="`About ${ingredient.food?.name || 'this ingredient'}`"
              @click.stop="openSheet(ingredient)"
            >
              <v-img
                v-if="ingredientImage(ingredient)"
                :src="ingredientImage(ingredient)!"
                cover
                width="34"
                height="34"
              />
              <v-icon
                v-else
                :icon="mdiFoodApple"
                size="17"
                class="ingredient-thumb__placeholder"
              />
            </button>
          </template>
          <v-list-item-title>
            <RecipeIngredientListItem
              :ingredient="ingredient"
              :scale="scale"
            />
          </v-list-item-title>
        </v-list-item>
      </div>
    </div>
    <IngredientSheet
      v-model="sheetOpen"
      :ingredient="sheetIngredient"
      :scale="scale"
    />
  </div>
</template>

<script setup lang="ts">
import { mdiFoodApple } from "@mdi/js";
import RecipeIngredientListItem from "./RecipeIngredientListItem.vue";
import IngredientSheet from "./IngredientSheet.vue";
import { useIngredientTextParser } from "~/composables/recipes";
import type { RecipeIngredient } from "~/lib/api/types/recipe";

interface Props {
  value?: RecipeIngredient[];
  scale?: number;
  isCookMode?: boolean;
}
const props = withDefaults(defineProps<Props>(), {
  value: () => [],
  scale: 1,
  isCookMode: false,
});

const { parseIngredientText } = useIngredientTextParser();

function validateTitle(title?: string | null) {
  return !(title === undefined || title === "" || title === null);
}

const checked = ref(props.value.map(() => false));
const showTitleEditor = computed(() => props.value.map(x => validateTitle(x.title)));

const ingredientCopyText = computed(() => {
  const components: string[] = [];
  props.value.forEach((ingredient) => {
    if (ingredient.title) {
      if (components.length) {
        components.push("");
      }

      components.push(`[${ingredient.title}]`);
    }

    components.push(parseIngredientText(ingredient, props.scale, false));
  });

  return components.join("\n");
});

function toggleChecked(index: number) {
  // TODO Find a better way to do this - $set is not available, and
  // direct array modifications are not propagated for some reason
  checked.value.splice(index, 1, !checked.value[index]);
}

// --- ingredient intelligence (fork) ---
const sheetOpen = ref(false);
const sheetIngredient = ref<RecipeIngredient | null>(null);

function ingredientImage(ingredient: RecipeIngredient): string | null {
  return (ingredient.food as { extras?: Record<string, string> } | undefined)?.extras?.image_url || null;
}

function openSheet(ingredient: RecipeIngredient) {
  sheetIngredient.value = ingredient;
  sheetOpen.value = true;
}
</script>

<style>
.dense-markdown p {
  margin: auto !important;
}

.ingredient-thumb {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  overflow: hidden;
  flex: 0 0 auto;
  background: rgba(var(--v-theme-primary), 0.06);
  border: 1px solid rgba(var(--v-border-color), 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.ingredient-thumb:hover {
  transform: scale(1.06);
  box-shadow: var(--ms-shadow-sm);
}

.ingredient-thumb__placeholder {
  opacity: 0.35;
}
</style>
