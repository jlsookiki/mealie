<template>
  <section>
    <div class="editor-section__header mb-3">
      <h2 class="editor-section__title">
        {{ $t("recipe.ingredients") }}
      </h2>
      <div class="editor-section__rule" />
    </div>

    <BannerWarning
      v-if="!hasFoodOrUnit && recipe.recipeIngredient.length > 0"
      class="mb-3"
    >
      {{ $t("recipe.ingredients-not-parsed-description", { parse: $t("recipe.parse") }) }}
    </BannerWarning>

    <VueDraggable
      v-if="recipe.recipeIngredient.length > 0"
      v-model="recipe.recipeIngredient"
      handle=".handle"
      :delay="250"
      :delay-on-touch-only="true"
      class="ingredients-list"
      v-bind="{
        animation: reduceMotion === 'reduce' ? 0 : 200,
        group: 'recipe-ingredients',
        disabled: false,
        ghostClass: 'ghost',
      }"
      @start="drag = true"
      @end="drag = false"
    >
      <TransitionGroup
        type="transition"
        :name="drag ? undefined : 'list-row'"
      >
        <RecipeEditorIngredientRow
          v-for="(ingredient, index) in recipe.recipeIngredient"
          :key="ingredient.referenceId"
          :ref="el => setRowRef(el, index)"
          v-model="recipe.recipeIngredient[index]"
          :is-recipe="ingredientIsRecipe(ingredient)"
          class="list-group-item"
          @delete="recipe.recipeIngredient.splice(index, 1)"
          @insert-above="insertNewIngredient(index)"
          @insert-below="insertNewIngredient(index + 1)"
          @note-enter="onNoteEnter(index)"
          @food-info="openFoodSheet(ingredient)"
        />
      </TransitionGroup>
    </VueDraggable>

    <div
      v-else
      class="ingredients-empty text-center py-6"
    >
      <p class="mb-0">
        No ingredients yet — add one below, or paste a list with bulk add.
      </p>
    </div>

    <div class="d-flex flex-wrap align-center ga-2 mt-3">
      <v-btn
        color="primary"
        variant="tonal"
        rounded="lg"
        @click="addAndFocus()"
      >
        <v-icon
          start
          :icon="mdiPlus"
        />
        Add ingredient
      </v-btn>
      <v-menu>
        <template #activator="{ props: menuProps }">
          <v-btn
            icon
            variant="tonal"
            color="primary"
            size="small"
            v-bind="menuProps"
          >
            <v-icon :icon="mdiChevronDown" />
          </v-btn>
        </template>
        <v-list density="comfortable">
          <v-list-item
            :title="$t('new-recipe.add-recipe')"
            @click="addRecipe()"
          />
          <v-list-item
            :title="$t('new-recipe.bulk-add')"
            @click="showBulkAdd"
          />
        </v-list>
      </v-menu>
      <v-spacer />
      <v-tooltip location="top">
        <template #activator="{ props: tipProps }">
          <span v-bind="tipProps">
            <v-btn
              variant="text"
              :disabled="hasFoodOrUnit"
              @click="toggleIsParsing(true)"
            >
              <v-icon
                start
                :icon="mdiAutoFix"
              />
              {{ $t("recipe.parse") }}
            </v-btn>
          </span>
        </template>
        <span>{{ parserToolTip }}</span>
      </v-tooltip>
      <RecipeDialogBulkAdd
        ref="domBulkAddDialog"
        style="display: none"
        @bulk-data="addIngredient"
      />
      <IngredientSheet
        v-model="foodSheetOpen"
        :ingredient="foodSheetIngredient"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { VueDraggable } from "vue-draggable-plus";
import { usePreferredReducedMotion } from "@vueuse/core";
import { mdiAutoFix, mdiChevronDown, mdiPlus } from "@mdi/js";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import type { Recipe, RecipeIngredient } from "~/lib/api/types/recipe";
import RecipeEditorIngredientRow from "~/components/Domain/Recipe/RecipeEditorIngredientRow.vue";
import RecipeDialogBulkAdd from "~/components/Domain/Recipe/RecipeDialogBulkAdd.vue";
import IngredientSheet from "~/components/Domain/Recipe/IngredientSheet.vue";
import { usePageState } from "~/composables/recipe-page/shared-state";
import { uuid4 } from "~/composables/use-utils";

const recipe = defineModel<NoUndefinedField<Recipe>>({ required: true });
const ingredientsWithRecipe = new Map<string, boolean>();
const i18n = useI18n();

const drag = ref(false);

// ingredient intelligence sheet (fork)
const foodSheetOpen = ref(false);
const foodSheetIngredient = ref<RecipeIngredient | null>(null);
function openFoodSheet(ingredient: RecipeIngredient) {
  foodSheetIngredient.value = ingredient;
  foodSheetOpen.value = true;
}
const domBulkAddDialog = ref<InstanceType<typeof RecipeDialogBulkAdd> | null>(null);
const { toggleIsParsing } = usePageState(recipe.value.slug);
const reduceMotion = usePreferredReducedMotion();

type RowInstance = InstanceType<typeof RecipeEditorIngredientRow> | null;
const rowRefs = ref<RowInstance[]>([]);

function setRowRef(el: any, index: number) {
  rowRefs.value[index] = el;
}

const hasFoodOrUnit = computed(() => {
  return (recipe.value?.recipeIngredient ?? []).some(ing => ing.food || ing.unit);
});

const parserToolTip = computed(() => {
  if (hasFoodOrUnit.value) {
    return i18n.t("recipe.recipes-with-units-or-foods-defined-cannot-be-parsed");
  }
  return i18n.t("recipe.parse-ingredients");
});

function showBulkAdd() {
  domBulkAddDialog.value?.open();
}

function ingredientIsRecipe(ingredient: RecipeIngredient): boolean {
  if (ingredient.referencedRecipe) {
    return true;
  }
  if (ingredient.referenceId) {
    return !!ingredientsWithRecipe.get(ingredient.referenceId);
  }
  return false;
}

function newIngredient(note = ""): RecipeIngredient {
  return {
    referenceId: uuid4(),
    title: "",
    note,
    unit: undefined,
    food: undefined,
    quantity: 0,
  };
}

function addIngredient(ingredients: Array<string> | null = null) {
  if (ingredients?.length) {
    // @ts-expect-error - nullable props vs NoUndefinedField
    recipe.value.recipeIngredient.push(...ingredients.map(x => newIngredient(x)));
  }
  else {
    // @ts-expect-error - nullable props vs NoUndefinedField
    recipe.value.recipeIngredient.push(newIngredient());
  }
}

function addRecipe() {
  const refId = uuid4();
  ingredientsWithRecipe.set(refId, true);
  recipe.value.recipeIngredient.push({
    referenceId: refId,
    title: "",
    note: "",
    // @ts-expect-error - nullable props vs NoUndefinedField
    unit: undefined,
    // @ts-expect-error - nullable props vs NoUndefinedField
    referencedRecipe: undefined,
    quantity: 1,
  });
}

function insertNewIngredient(dest: number) {
  // @ts-expect-error - nullable props vs NoUndefinedField
  recipe.value.recipeIngredient.splice(dest, 0, newIngredient());
  focusRow(dest);
}

async function addAndFocus() {
  addIngredient();
  focusRow(recipe.value.recipeIngredient.length - 1);
}

async function focusRow(index: number) {
  await nextTick();
  rowRefs.value[index]?.focusNote();
}

function onNoteEnter(index: number) {
  const current = recipe.value.recipeIngredient[index];
  if (!current?.note?.trim() && !current?.food && !current?.quantity) {
    return; // empty row — don't spawn more
  }
  if (index === recipe.value.recipeIngredient.length - 1) {
    addAndFocus();
  }
  else {
    insertNewIngredient(index + 1);
  }
}
</script>

<style scoped>
.ingredients-list {
  position: relative;
}

.editor-section__header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.editor-section__title {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.2;
}

.editor-section__rule {
  width: 44px;
  height: 3px;
  border-radius: 2px;
  background: rgb(var(--v-theme-primary));
}

.ingredients-empty {
  border: 1px dashed rgba(var(--v-border-color), 0.25);
  border-radius: var(--ms-radius-lg);
  opacity: 0.7;
}
</style>
