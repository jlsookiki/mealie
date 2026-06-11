<template>
  <section @keyup.ctrl.z="undoMerge">
    <!-- Ingredient Link Editor -->
    <BaseDialog
      v-model="dialog"
      :title="$t('recipe.ingredient-linker')"
      :icon="$globals.icons.link"
      width="100%"
      max-width="600px"
      max-height="40%"
    >
      <v-card-text class="pt-4">
        <p>{{ activeText }}</p>
        <v-divider class="my-4" />
        <template v-if="Object.keys(groupedUnusedIngredients).length > 0">
          <h4 class="ml-1">
            {{ $t("recipe.unlinked") }}
          </h4>
          <template
            v-for="(ingredients, title) in groupedUnusedIngredients"
            :key="title"
          >
            <h4
              v-if="title"
              class="py-3 ml-1 pl-4"
            >
              {{ title }}
            </h4>
            <v-checkbox-btn
              v-for="ing in ingredients"
              :key="ing.referenceId"
              v-model="activeRefs"
              :value="ing.referenceId"
              class="ml-4"
            >
              <template #label>
                <RecipeIngredientHtml
                  :ingredient="ing"
                  :scale="1"
                />
              </template>
            </v-checkbox-btn>
          </template>
        </template>

        <template v-if="Object.keys(groupedUsedIngredients).length > 0">
          <h4 class="py-3 ml-1">
            {{ $t("recipe.linked-to-other-step") }}
          </h4>
          <template
            v-for="(ingredients, title) in groupedUsedIngredients"
            :key="title"
          >
            <h4
              v-if="title"
              class="py-3 ml-1 pl-4"
            >
              {{ title }}
            </h4>
            <v-checkbox-btn
              v-for="ing in ingredients"
              :key="ing.referenceId"
              v-model="activeRefs"
              :value="ing.referenceId"
              class="ml-4"
            >
              <template #label>
                <RecipeIngredientHtml
                  :ingredient="ing"
                  :scale="1"
                />
              </template>
            </v-checkbox-btn>
          </template>
        </template>
      </v-card-text>

      <v-divider />

      <template #card-actions>
        <BaseButton
          cancel
          @click="dialog = false"
        />
        <v-spacer />
        <div class="d-flex flex-wrap justify-end">
          <BaseButton
            class="my-1"
            color="info"
            @click="autoSetReferences"
          >
            <template #icon>
              {{ $globals.icons.robot }}
            </template>
            {{ $t("recipe.auto") }}
          </BaseButton>
          <BaseButton
            class="ml-2 my-1"
            save
            @click="setIngredientIds"
          />
          <BaseButton
            v-if="availableNextStep"
            class="ml-2 my-1"
            @click="saveAndOpenNextLinkIngredients"
          >
            <template #icon>
              {{ $globals.icons.forward }}
            </template>
            {{ $t("recipe.nextStep") }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <div class="editor-section__header mb-3">
      <h2 class="editor-section__title">
        {{ $t("recipe.instructions") }}
      </h2>
      <div class="editor-section__rule" />
    </div>

    <VueDraggable
      v-model="instructionList"
      handle=".handle"
      :delay="250"
      :delay-on-touch-only="true"
      class="steps-list"
      v-bind="{
        animation: reduceMotion === 'reduce' ? 0 : 200,
        group: 'recipe-instructions',
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
        <div
          v-for="(step, index) in instructionList"
          :key="step.id ?? index"
          class="list-group-item"
        >
          <!-- Section title band -->
          <div
            v-if="showTitleEditor[step.id ?? '']"
            class="step-card__section mb-2"
          >
            <v-text-field
              v-model="step.title"
              density="compact"
              variant="plain"
              hide-details
              :placeholder="$t('recipe.section-title')"
              class="step-card__section-field px-3"
            />
          </div>

          <div class="editor-row step-card mb-3">
            <div class="step-card__header d-flex align-center px-3 pt-2">
              <v-icon
                class="handle mr-1"
                :icon="mdiDragVertical"
              />
              <span class="step-card__number mr-3">Step {{ index + 1 }}</span>
              <v-text-field
                v-model="step.summary"
                hide-details
                density="compact"
                variant="plain"
                placeholder="Optional summary"
                class="step-card__summary"
              />
              <div class="step-card__actions d-flex align-center">
                <v-btn
                  v-tooltip="$t('recipe.link-ingredients')"
                  icon
                  size="x-small"
                  variant="text"
                  @click="openDialog(index, step.text, step.ingredientReferences)"
                >
                  <v-icon :icon="mdiLinkVariant" />
                </v-btn>
                <v-btn
                  v-tooltip="$t('recipe.upload-image')"
                  icon
                  size="x-small"
                  variant="text"
                  @click="openImageUpload(index)"
                >
                  <v-icon :icon="mdiImageOutline" />
                </v-btn>
                <v-btn
                  v-tooltip="previewStates[index] ? 'Edit' : 'Preview'"
                  icon
                  size="x-small"
                  variant="text"
                  @click="togglePreviewState(index)"
                >
                  <v-icon :icon="previewStates[index] ? mdiPencil : mdiEyeOutline" />
                </v-btn>
                <v-btn
                  v-tooltip="$t('general.delete')"
                  icon
                  size="x-small"
                  variant="text"
                  @click="instructionList.splice(index, 1)"
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
                    <v-list-item @click="toggleShowTitle(step.id)">
                      <v-list-item-title>{{ $t("recipe.toggle-section") }}</v-list-item-title>
                    </v-list-item>
                    <v-divider class="my-1" />
                    <v-list-item
                      :disabled="index === 0"
                      @click="mergeAbove(index - 1, index)"
                    >
                      <v-list-item-title>{{ $t("recipe.merge-above") }}</v-list-item-title>
                    </v-list-item>
                    <v-list-item @click="moveTo('top', index)">
                      <v-list-item-title>{{ $t("recipe.move-to-top") }}</v-list-item-title>
                    </v-list-item>
                    <v-list-item @click="moveTo('bottom', index)">
                      <v-list-item-title>{{ $t("recipe.move-to-bottom") }}</v-list-item-title>
                    </v-list-item>
                    <v-divider class="my-1" />
                    <v-list-item @click="insert(index)">
                      <v-list-item-title>{{ $t("recipe.insert-above") }}</v-list-item-title>
                    </v-list-item>
                    <v-list-item @click="insert(index + 1)">
                      <v-list-item-title>{{ $t("recipe.insert-below") }}</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </div>
            </div>

            <v-progress-linear
              v-if="loadingStates[index]"
              :active="true"
              :indeterminate="true"
              color="primary"
            />

            <DropZone @drop="f => handleImageDrop(index, f)">
              <div class="px-3 pb-3">
                <MarkdownEditor
                  v-model="instructionList[index]['text']"
                  v-model:preview="previewStates[index]"
                  class="mb-1"
                  :display-preview="false"
                  :textarea="{
                    hint: $t('recipe.attach-images-hint'),
                    persistentHint: true,
                  }"
                />
                <div
                  v-if="step.ingredientReferences && step.ingredientReferences.length"
                  class="step-card__linked pt-2"
                >
                  <div
                    v-for="(linkRef, i) in step.ingredientReferences"
                    :key="linkRef.referenceId ?? i"
                    class="mb-1"
                  >
                    <RecipeIngredientHtml
                      v-if="linkRef.referenceId && ingredientLookup[linkRef.referenceId]"
                      :ingredient="ingredientLookup[linkRef.referenceId]"
                      :scale="1"
                    />
                  </div>
                </div>
              </div>
            </DropZone>
          </div>
        </div>
      </TransitionGroup>
    </VueDraggable>

    <div
      v-if="instructionList.length === 0"
      class="steps-empty text-center py-6 mb-3"
    >
      <p class="mb-0">
        No steps yet — write the first one below.
      </p>
    </div>

    <div class="d-flex flex-wrap align-center ga-2">
      <v-btn
        color="primary"
        variant="tonal"
        rounded="lg"
        @click="addStep()"
      >
        <v-icon
          start
          :icon="mdiPlus"
        />
        Add step
      </v-btn>
      <RecipeDialogBulkAdd @bulk-data="addStep" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { VueDraggable } from "vue-draggable-plus";
import { usePreferredReducedMotion } from "@vueuse/core";
import {
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiDragVertical,
  mdiEyeOutline,
  mdiImageOutline,
  mdiLinkVariant,
  mdiPencil,
  mdiPlus,
} from "@mdi/js";
import type { RecipeStep, IngredientReferences, RecipeIngredient, RecipeAsset, Recipe } from "~/lib/api/types/recipe";
import { uuid4 } from "~/composables/use-utils";
import { useUserApi, useStaticRoutes } from "~/composables/api";
import { useExtractIngredientReferences } from "~/composables/recipe-page/use-extract-ingredient-references";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import DropZone from "~/components/global/DropZone.vue";
import RecipeIngredientHtml from "~/components/Domain/Recipe/RecipeIngredientHtml.vue";
import RecipeDialogBulkAdd from "~/components/Domain/Recipe/RecipeDialogBulkAdd.vue";

interface MergerHistory {
  target: number;
  source: number;
  targetText: string;
  sourceText: string;
}

const instructionList = defineModel<RecipeStep[]>("modelValue", { required: true, default: () => [] });
const assets = defineModel<RecipeAsset[]>("assets", { required: true, default: () => [] });

const props = defineProps({
  recipe: {
    type: Object as () => NoUndefinedField<Recipe>,
    required: true,
  },
});

const emit = defineEmits(["update:assets"]);

const { $globals } = useNuxtApp();
const { extractIngredientReferences } = useExtractIngredientReferences();
const reduceMotion = usePreferredReducedMotion();

const drag = ref(false);
const dialog = ref(false);
const unusedIngredients = ref<RecipeIngredient[]>([]);
const usedIngredients = ref<RecipeIngredient[]>([]);
const showTitleEditor = ref<{ [key: string]: boolean }>({});
const previewStates = ref<boolean[]>([]);

function hasSectionTitle(title: string | undefined | null) {
  return !(title === null || title === "" || title === undefined);
}

onMounted(() => {
  instructionList.value.forEach((element: RecipeStep) => {
    if (element.id !== undefined && element.id !== null) {
      showTitleEditor.value[element.id] = hasSectionTitle(element.title);
    }
  });
  showTitleEditor.value = { ...showTitleEditor.value };

  if (assets.value === undefined) {
    emit("update:assets", []);
  }
});

function toggleShowTitle(id?: string | null) {
  if (!id) {
    return;
  }
  showTitleEditor.value[id] = !showTitleEditor.value[id];
  const step = instructionList.value.find(s => s.id === id);
  if (step && !showTitleEditor.value[id]) {
    step.title = "";
  }
  showTitleEditor.value = { ...showTitleEditor.value };
}

function togglePreviewState(index: number) {
  const temp = [...previewStates.value];
  temp[index] = !temp[index];
  previewStates.value = temp;
}

function addStep(steps: Array<string> | null = null) {
  if (steps?.length) {
    instructionList.value.push(
      ...steps.map(text => ({ id: uuid4(), text, title: "", ingredientReferences: [] })),
    );
  }
  else {
    instructionList.value.push({ id: uuid4(), text: "", title: "", ingredientReferences: [] });
  }
}

// ===============================================================
// Ingredient Linker (ported from RecipePageInstructions)
const activeRefs = ref<string[]>([]);
const activeIndex = ref(0);
const activeText = ref("");

function openDialog(idx: number, text: string, refs?: IngredientReferences[]) {
  if (!refs) {
    instructionList.value[idx].ingredientReferences = [];
    refs = instructionList.value[idx].ingredientReferences as IngredientReferences[];
  }
  activeIndex.value = idx;
  activeText.value = text;
  setUsedIngredients();
  dialog.value = true;
  activeRefs.value = refs.map(r => r.referenceId ?? "");
}

const availableNextStep = computed(() => activeIndex.value < instructionList.value.length - 1);

function setIngredientIds() {
  const instruction = instructionList.value[activeIndex.value];
  instruction.ingredientReferences = activeRefs.value.map(r => ({ referenceId: r }));
  dialog.value = false;
}

function saveAndOpenNextLinkIngredients() {
  const currentStepIndex = activeIndex.value;
  if (!availableNextStep.value) {
    return;
  }
  setIngredientIds();
  const nextStep = instructionList.value[currentStepIndex + 1];
  nextTick(() => openDialog(currentStepIndex + 1, nextStep.text, nextStep.ingredientReferences));
}

function setUsedIngredients() {
  const usedRefs: { [key: string]: boolean } = {};
  instructionList.value.forEach((element, idx) => {
    if (idx === activeIndex.value) {
      return;
    }
    element.ingredientReferences?.forEach((r) => {
      if (r.referenceId) {
        usedRefs[r.referenceId] = true;
      }
    });
  });

  usedIngredients.value = props.recipe.recipeIngredient.filter(ing => !!ing.referenceId && ing.referenceId in usedRefs);
  unusedIngredients.value = props.recipe.recipeIngredient.filter(ing => !!ing.referenceId && !(ing.referenceId in usedRefs));
}

watch(activeRefs, () => setUsedIngredients());

function autoSetReferences() {
  extractIngredientReferences(
    props.recipe.recipeIngredient,
    activeRefs.value,
    activeText.value,
  ).forEach(ingredient => activeRefs.value.push(ingredient));
}

const ingredientLookup = computed(() => {
  const results: { [key: string]: RecipeIngredient } = {};
  return props.recipe.recipeIngredient.reduce((prev, ing) => {
    if (ing.referenceId === undefined) {
      return prev;
    }
    prev[ing.referenceId] = ing;
    return prev;
  }, results);
});

const ingredientSectionTitles = computed(() => {
  const titleMap: { [key: string]: string } = {};
  let currentTitle = "";
  props.recipe.recipeIngredient.forEach((ingredient) => {
    if (ingredient.referenceId === undefined) {
      return;
    }
    if (ingredient.title) {
      currentTitle = ingredient.title;
    }
    titleMap[ingredient.referenceId] = currentTitle;
  });
  return titleMap;
});

const groupedUnusedIngredients = computed((): Record<string, RecipeIngredient[]> => {
  const groups: Record<string, RecipeIngredient[]> = {};
  unusedIngredients.value.forEach((ingredient) => {
    if (ingredient.referenceId === undefined) {
      return;
    }
    const title = ingredientSectionTitles.value[ingredient.referenceId] || ingredient.title || "";
    (groups[title] ||= []).push(ingredient);
  });
  return groups;
});

const groupedUsedIngredients = computed((): Record<string, RecipeIngredient[]> => {
  const groups: Record<string, RecipeIngredient[]> = {};
  usedIngredients.value.forEach((ingredient) => {
    if (ingredient.referenceId === undefined) {
      return;
    }
    const title = ingredientSectionTitles.value[ingredient.referenceId] || ingredient.title || "";
    (groups[title] ||= []).push(ingredient);
  });
  return groups;
});

// ===============================================================
// Instruction Merger
const mergeHistory = ref<MergerHistory[]>([]);

function mergeAbove(target: number, source: number) {
  if (target < 0) {
    return;
  }
  mergeHistory.value.push({
    target,
    source,
    targetText: instructionList.value[target].text,
    sourceText: instructionList.value[source].text,
  });
  instructionList.value[target].text += " " + instructionList.value[source].text;
  instructionList.value.splice(source, 1);
}

function undoMerge(event: KeyboardEvent) {
  if (event.ctrlKey && event.code === "KeyZ") {
    if (!(mergeHistory.value?.length > 0)) {
      return;
    }
    const lastMerge = mergeHistory.value.pop();
    if (!lastMerge) {
      return;
    }
    instructionList.value[lastMerge.target].text = lastMerge.targetText;
    instructionList.value.splice(lastMerge.source, 0, {
      id: uuid4(),
      title: "",
      text: lastMerge.sourceText,
      ingredientReferences: [],
    });
  }
}

function moveTo(dest: string, source: number) {
  if (dest === "top") {
    instructionList.value.unshift(instructionList.value.splice(source, 1)[0]);
  }
  else {
    instructionList.value.push(instructionList.value.splice(source, 1)[0]);
  }
}

function insert(dest: number) {
  instructionList.value.splice(dest, 0, { id: uuid4(), text: "", title: "", ingredientReferences: [] });
}

// ===============================================================
// Step image upload
const api = useUserApi();
const { recipeAssetPath } = useStaticRoutes();
const loadingStates = ref<{ [key: number]: boolean }>({});

async function handleImageDrop(index: number, files: File[]) {
  if (!files) {
    return;
  }
  const file = files[0];
  if (!file || !file.type.startsWith("image/")) {
    return;
  }

  loadingStates.value[index] = true;
  const { data } = await api.recipes.createAsset(props.recipe.slug, {
    name: file.name,
    icon: "mdi-file-image",
    file,
    extension: file.name.split(".").pop() || "",
  });
  loadingStates.value[index] = false;

  if (!data) {
    return;
  }

  emit("update:assets", [...assets.value, data]);
  const assetUrl = recipeAssetPath(props.recipe.id, data.fileName as string);
  instructionList.value[index].text += `<img src="${assetUrl}" height="100%" width="100%"/>`;
}

function openImageUpload(index: number) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.onchange = async () => {
    if (input.files) {
      await handleImageDrop(index, Array.from(input.files));
      input.remove();
    }
  };
  input.click();
}
</script>

<style scoped>
.steps-list {
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

.step-card {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), 0.1);
  border-radius: var(--ms-radius-lg);
  overflow: hidden;
  transition:
    box-shadow var(--ms-dur-fast) var(--ms-ease),
    border-color var(--ms-dur-fast) var(--ms-ease);
}

.step-card:hover,
.step-card:focus-within {
  box-shadow: var(--ms-shadow-sm);
  border-color: rgba(var(--v-border-color), 0.2);
}

.step-card__number {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 1.05rem;
  white-space: nowrap;
}

.step-card__summary {
  min-width: 120px;
}

.step-card__actions {
  opacity: 0.25;
  transition: opacity var(--ms-dur-fast) var(--ms-ease);
}

.step-card:hover .step-card__actions,
.step-card:focus-within .step-card__actions {
  opacity: 1;
}

.step-card__section {
  background: rgba(var(--v-theme-primary), 0.08);
  border-radius: var(--ms-radius-lg);
}

.step-card__section-field :deep(input) {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 1.05rem;
}

.step-card__linked {
  border-top: 1px dashed rgba(var(--v-border-color), 0.15);
}

.steps-empty {
  border: 1px dashed rgba(var(--v-border-color), 0.25);
  border-radius: var(--ms-radius-lg);
  opacity: 0.7;
}
</style>
