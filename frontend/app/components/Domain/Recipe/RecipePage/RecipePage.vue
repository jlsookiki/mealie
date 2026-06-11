<template>
  <div>
    <BaseDialog
      v-model="discardDialog"
      :title="$t('general.discard-changes')"
      color="warning"
      :icon="$globals.icons.alertCircle"
      can-confirm
      @confirm="confirmDiscard"
      @cancel="cancelDiscard"
    >
      <v-card-text>
        {{ $t("general.discard-changes-description") }}
      </v-card-text>
    </BaseDialog>
    <RecipePageParseDialog
      :model-value="isParsing"
      :ingredients="recipe.recipeIngredient"
      :width="$vuetify.display.smAndDown ? '100%' : '80%'"
      @update:model-value="toggleIsParsing"
      @save="saveParsedIngredients"
    />
    <RecipePageEditorSettings
      v-model="settingsOpen"
      v-model:recipe="recipe"
    />
    <v-container v-show="!isCookMode" key="recipe-page" class="px-0" :class="{ 'pa-0': $vuetify.display.smAndDown }">
      <!-- Keyed by mode so the whole subtree remounts on view<->edit, guaranteeing
           slot re-render and a clean entrance for the editor's staggered animations. -->
      <v-card :key="isEditMode ? 'editor' : 'viewer'" flat class="d-print-none" :class="{ 'recipe-editor': isEditMode }">
        <RecipePageHeader
          v-if="!isEditMode"
          :recipe="recipe"
          :recipe-scale="scale"
          :landscape="landscape"
          @save="saveRecipe"
          @delete="deleteRecipe"
          @close="closeEditor"
        />
        <RecipePageEditorBar
          v-if="isEditMode"
          :name="recipe.name || ''"
          :dirty="isDirty"
          :save-state="saveState"
          :is-json-mode="isEditJSON"
          @save="saveRecipe"
          @close="closeEditor"
          @delete="deleteRecipe"
          @toggle-json="toggleEditMode"
          @open-settings="settingsOpen = true"
        />
        <RecipeJsonEditor
          v-if="isEditJSON"
          v-model="recipe"
          class="mt-10"
          mode="text"
          :main-menu-bar="false"
        />
        <v-card-text v-else>
          <!--
            This is where most of the main content is rendered. Some components include state for both Edit and View modes
            which is why some have explicit v-if statements and others use the composition API to determine and manage
            the shared state internally.

            The global recipe object is shared down the tree of components and _is_ mutated by child components. This is
            some-what of a hack of the system and goes against the principles of Vue, but it _does_ seem to work and streamline
            a significant amount of prop management. When we move to Vue 3 and have access to some of the newer API's the plan to update this
            data management and mutation system we're using.
          -->
          <RecipePageEditorHero
            v-if="isEditForm"
            v-model="recipe"
            class="editor-section mb-6"
            style="--editor-stagger: 0"
            @image-updated="syncImageSnapshot"
          />
          <div
            v-if="isEditMode"
            class="editor-section"
            style="--editor-stagger: 1"
          >
            <RecipePageInfoEditor v-model="recipe" />
          </div>
          <RecipeEditorIngredients
            v-if="isEditForm"
            v-model="recipe"
            class="editor-section mt-6"
            style="--editor-stagger: 2"
          />
          <div v-if="!isEditMode">
            <RecipePageScale v-model="scale" :recipe="recipe" />
          </div>

          <!--
            This section contains the 2 column layout for the recipe steps and other content.
          -->
          <v-row>
            <!--
              The left column is conditionally rendered based on cook mode.
            -->
            <v-col
              v-if="!isCookMode || isEditForm"
              cols="12"
              sm="12"
              md="4"
              :class="$vuetify.display.mdAndUp ? 'border-e-thin' : null"
            >
              <RecipePageIngredientToolsView v-if="!isEditForm" :recipe="recipe" :scale="scale" class="pr-2" />
              <RecipePageOrganizers v-if="$vuetify.display.mdAndUp" v-model="recipe" class="pr-2" @item-selected="chipClicked" />
            </v-col>
            <!--
              the right column is always rendered, but it's layout width is determined by where the left column is
              rendered.
            -->
            <v-col cols="12" sm="12" :md="8 + (isCookMode ? 1 : 0) * 4">
              <RecipePageInstructions
                v-if="!isEditForm"
                v-model="recipe.recipeInstructions"
                v-model:assets="recipe.assets"
                :recipe="recipe"
                :scale="scale"
              />
              <RecipeEditorSteps
                v-else
                v-model="recipe.recipeInstructions"
                v-model:assets="recipe.assets"
                :recipe="recipe"
                class="editor-section"
                style="--editor-stagger: 3"
              />
              <div v-if="!$vuetify.display.mdAndUp">
                <RecipePageOrganizers v-model="recipe" />
              </div>
              <RecipeNotes v-model="recipe.notes" :edit="isEditForm" />
            </v-col>
          </v-row>
          <RecipePageFooter v-model="recipe" />
        </v-card-text>
      </v-card>
      <WakelockSwitch />
      <RecipePageComments
        v-if="!recipe.settings?.disableComments && !isEditForm && !isCookMode"
        v-model="recipe"
        class="px-1 my-4 d-print-none"
      />
      <RecipePrintContainer :recipe="recipe" :scale="scale" />
    </v-container>
    <!-- Cook mode displayes two columns with ingredients and instructions side by side, each being scrolled individually, allowing to view both at the same time -->
    <!-- The calc is to account for the navabar height (48px) -->
    <v-sheet
      v-show="isCookMode && !hasLinkedIngredients"
      key="cookmode"
      :height="$vuetify.display.smAndUp ? 'calc(100vh - 48px)' : 'auto'"
      class-name="overflow-hidden"
    >
      <!-- the calc is to account for the toolbar a more dynamic solution could be needed  -->
      <v-row style="height: 100%" no-gutters class="overflow-hidden">
        <v-col cols="12" sm="5" class="overflow-y-auto pl-4 pr-3 py-2" style="height: 100%">
          <div class="d-flex align-center">
            <RecipePageScale v-model="scale" :recipe="recipe" />
          </div>
          <RecipePageIngredientToolsView
            v-if="!isEditForm"
            :recipe="recipe"
            :scale="scale"
            :is-cook-mode="isCookMode"
          />
          <v-divider />
        </v-col>
        <v-col
          class="overflow-y-auto"
          :class="$vuetify.display.smAndDown ? 'py-2': 'py-6'"
          style="height: 100%"
          cols="12"
          sm="7"
        >
          <h2 class="text-h5 px-4 font-weight-medium opacity-80">
            {{ $t('recipe.instructions') }}
          </h2>
          <RecipePageInstructions
            v-model="recipe.recipeInstructions"
            v-model:assets="recipe.assets"
            class="overflow-y-hidden px-4"
            :recipe="recipe"
            :scale="scale"
          />
        </v-col>
      </v-row>
    </v-sheet>
    <v-sheet v-show="isCookMode && hasLinkedIngredients">
      <div class="mt-2 px-2 px-md-4">
        <RecipePageScale v-model="scale" :recipe="recipe" />
      </div>
      <RecipePageInstructions
        v-model="recipe.recipeInstructions"
        v-model:assets="recipe.assets"
        class="overflow-y-hidden mt-n5 px-2 px-md-4"
        :recipe="recipe"
        :scale="scale"
      />

      <div v-if="notLinkedIngredients.length > 0" class="px-2 px-md-4 pb-4">
        <v-divider />
        <v-card flat>
          <v-card-title>{{ $t("recipe.not-linked-ingredients") }}</v-card-title>
          <RecipeIngredients
            :value="notLinkedIngredients"
            :scale="scale"
            :is-cook-mode="isCookMode"
          />
        </v-card>
      </div>
    </v-sheet>
    <v-btn
      v-if="isCookMode"
      icon
      color="primary"
      style="position: fixed; right: 12px; top: 60px"
      @click="toggleCookMode()"
    >
      <v-icon>{{ $globals.icons.close }}</v-icon>
    </v-btn>
  </div>
</template>

<script setup lang="ts">
import { invoke, until, watchDebounced } from "@vueuse/core";
import type { RouteLocationNormalized } from "vue-router";
import RecipeIngredients from "../RecipeIngredients.vue";
import RecipePageEditorBar from "./RecipePageParts/RecipePageEditorBar.vue";
import RecipePageEditorHero from "./RecipePageParts/RecipePageEditorHero.vue";
import RecipePageEditorSettings from "./RecipePageParts/RecipePageEditorSettings.vue";
import RecipePageFooter from "./RecipePageParts/RecipePageFooter.vue";
import RecipePageHeader from "./RecipePageParts/RecipePageHeader.vue";
import RecipeEditorIngredients from "./RecipePageParts/RecipeEditorIngredients.vue";
import RecipePageIngredientToolsView from "./RecipePageParts/RecipePageIngredientToolsView.vue";
import RecipePageInstructions from "./RecipePageParts/RecipePageInstructions.vue";
import RecipePageOrganizers from "./RecipePageParts/RecipePageOrganizers.vue";
import RecipePageParseDialog from "./RecipePageParts/RecipePageParseDialog.vue";
import RecipePageScale from "./RecipePageParts/RecipePageScale.vue";
import RecipePageInfoEditor from "./RecipePageParts/RecipePageInfoEditor.vue";
import RecipePageComments from "./RecipePageParts/RecipePageComments.vue";
import RecipePrintContainer from "~/components/Domain/Recipe/RecipePrintContainer.vue";
import {
  clearPageState,
  PageMode,
  usePageState,
} from "~/composables/recipe-page/shared-state";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import type { Recipe, RecipeCategory, RecipeIngredient, RecipeTag, RecipeTool } from "~/lib/api/types/recipe";
import { useRouteQuery } from "~/composables/use-router";
import { useUserApi } from "~/composables/api";
import { deepCopy } from "~/composables/use-utils";
import RecipeEditorSteps from "./RecipePageParts/RecipeEditorSteps.vue";
import RecipeNotes from "~/components/Domain/Recipe/RecipeNotes.vue";
import { useLoggedInState } from "~/composables/use-logged-in-state";
import { useNavigationWarning } from "~/composables/use-navigation-warning";

const recipe = defineModel<NoUndefinedField<Recipe>>({ required: true });

const display = useDisplay();
const auth = useMealieAuth();
const route = useRoute();
const { isOwnGroup } = useLoggedInState();

const groupSlug = computed(() => (route.params.groupSlug as string) || auth.user?.value?.groupSlug || "");

const router = useRouter();
const api = useUserApi();
const { setMode, isEditForm, isEditJSON, isCookMode, isEditMode, isParsing, toggleCookMode, toggleIsParsing, toggleEditMode, saveState, isDirty }
  = usePageState(recipe.value.slug);
const { deactivateNavigationWarning } = useNavigationWarning();
const notLinkedIngredients = computed(() => {
  return recipe.value.recipeIngredient.filter((ingredient) => {
    return !recipe.value.recipeInstructions.some(step =>
      step.ingredientReferences?.map(ref => ref.referenceId).includes(ingredient.referenceId),
    );
  });
});

/** =============================================================
 * Recipe Snapshot on Mount
 * this is used to determine if the recipe has been changed since the last save
 * and prompts the user to save if they have unsaved changes.
 */
const originalRecipe = ref<Recipe | null>(null);
const discardDialog = ref(false);
const pendingRoute = ref<RouteLocationNormalized | null>(null);
const settingsOpen = ref(false);

useSaveShortcut(
  () => saveRecipe(),
  () => isEditMode.value && !discardDialog.value && !isParsing.value && !settingsOpen.value,
);

invoke(async () => {
  await until(recipe.value).not.toBeNull();
  originalRecipe.value = deepCopy(recipe.value);
});

function hasUnsavedChanges(): boolean {
  if (originalRecipe.value === null) {
    return false;
  }
  return JSON.stringify(recipe.value) !== JSON.stringify(originalRecipe.value);
}

// Debounced mirror of hasUnsavedChanges for UI (the dirty dot); guards keep
// using the synchronous compare so a fast edit→cancel is never missed.
watchDebounced(
  recipe,
  () => {
    isDirty.value = hasUnsavedChanges();
  },
  { debounce: 400, deep: true },
);

// Keep the dirty indicator honest for image operations, which persist
// immediately via their own endpoints rather than through saveRecipe.
function syncImageSnapshot() {
  if (originalRecipe.value) {
    originalRecipe.value.image = recipe.value.image;
    isDirty.value = hasUnsavedChanges();
  }
}

function restoreOriginalRecipe() {
  if (originalRecipe.value) {
    recipe.value = deepCopy(originalRecipe.value) as NoUndefinedField<Recipe>;
  }
}

function closeEditor() {
  if (hasUnsavedChanges()) {
    pendingRoute.value = null;
    discardDialog.value = true;
  }
  else {
    setMode(PageMode.VIEW);
  }
}

function confirmDiscard() {
  restoreOriginalRecipe();
  discardDialog.value = false;

  if (pendingRoute.value) {
    const destination = pendingRoute.value;
    pendingRoute.value = null;
    router.push(destination);
  }
  else {
    setMode(PageMode.VIEW);
  }
}

function cancelDiscard() {
  discardDialog.value = false;
  pendingRoute.value = null;
}

onBeforeRouteLeave((to) => {
  if (isEditMode.value && hasUnsavedChanges()) {
    pendingRoute.value = to;
    discardDialog.value = true;
    return false;
  }
});

onUnmounted(() => {
  deactivateNavigationWarning();
  toggleCookMode();
  clearPageState(recipe.value.slug || "");
});
const hasLinkedIngredients = computed(() => {
  return recipe.value.recipeInstructions.some(
    step => step.ingredientReferences && step.ingredientReferences.length > 0,
  );
});
/** =============================================================
 * Set State onMounted
 */

type BooleanString = "true" | "false" | "";

const paramsEdit = useRouteQuery<BooleanString>("edit", "");
const paramsParse = useRouteQuery<BooleanString>("parse", "");

onMounted(() => {
  if (paramsEdit.value === "true" && isOwnGroup.value) {
    setMode(PageMode.EDIT);
  }

  if (paramsParse.value === "true" && isOwnGroup.value) {
    toggleIsParsing(true);
  }
});

// When set, the isEditMode watcher skips its URL cleanup because saveRecipe
// is navigating to a new slug that naturally omits ?edit=true.
const isNavigatingAfterRename = ref(false);

watch(isEditMode, (newVal) => {
  if (!newVal) {
    if (isNavigatingAfterRename.value) {
      isNavigatingAfterRename.value = false;
      return;
    }
    paramsEdit.value = undefined;
  }
});

watch(isParsing, () => {
  if (!isParsing.value) {
    paramsParse.value = undefined;
  }
});

/** =============================================================
 * Recipe Save Delete
 */

async function saveRecipe() {
  if (saveState.value !== "idle") {
    return;
  }
  saveState.value = "saving";

  const { data, error } = await api.recipes.updateOne(recipe.value.slug, recipe.value);

  if (error) {
    saveState.value = "error";
    setTimeout(() => (saveState.value = "idle"), 600);
    return;
  }

  if (data?.slug) {
    recipe.value = data as NoUndefinedField<Recipe>;
    originalRecipe.value = deepCopy(recipe.value);
  }
  isDirty.value = false;
  saveState.value = "success";

  // Let the "Saved" beat land before flipping back to view mode.
  setTimeout(() => {
    if (data?.slug && data.slug !== route.params.slug) {
      isNavigatingAfterRename.value = true;
    }
    setMode(PageMode.VIEW);
    if (data?.slug && data.slug !== route.params.slug) {
      router.replace(`/g/${groupSlug.value}/r/` + data.slug);
    }
    saveState.value = "idle";
  }, 900);
}

async function saveParsedIngredients(ingredients: NoUndefinedField<RecipeIngredient[]>) {
  recipe.value.recipeIngredient = ingredients;
  await saveRecipe();
  toggleIsParsing(false);
}

async function deleteRecipe() {
  const { data } = await api.recipes.deleteOne(recipe.value.slug);
  if (data?.slug) {
    router.push(`/g/${groupSlug.value}`);
  }
}

/** =============================================================
 * View Preferences
 */
const landscape = computed(() => {
  const preferLandscape = recipe.value.settings?.landscapeView;
  const smallScreen = !display.smAndUp.value;

  if (preferLandscape) {
    return true;
  }
  else if (smallScreen) {
    return true;
  }

  return false;
});

/** =============================================================
 * RecipeChip Clicked
 */

function chipClicked(item: RecipeTag | RecipeCategory | RecipeTool, itemType: string) {
  if (!item.id) {
    return;
  }
  router.push(`/g/${groupSlug.value}?${itemType}=${item.id}`);
}

const scale = ref(1);

// expose to template
// (all variables used in template are top-level in <script setup>)
</script>

<style lang="css">
.flip-list-move {
  transition: transform 0.5s;
}

.no-move {
  transition: transform 0s;
}

.ghost {
  opacity: 0.5;
}

.list-group {
  min-height: 38px;
}

.list-group-item i {
  cursor: pointer;
}
</style>
