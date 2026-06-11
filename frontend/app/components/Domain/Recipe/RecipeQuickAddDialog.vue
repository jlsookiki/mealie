<template>
  <v-dialog
    v-model="dialog"
    max-width="580"
    :fullscreen="$vuetify.display.xs"
    @update:model-value="onDialogToggle"
  >
    <v-card
      rounded="xl"
      class="quick-add"
    >
      <div class="d-flex align-start px-6 pt-6 pb-1">
        <div>
          <h2 class="text-h5 mb-1">
            Add a recipe
          </h2>
          <p class="text-body-2 quick-add__muted ma-0">
            Paste a link, drop in recipe text, or just type a name.
          </p>
        </div>
        <v-spacer />
        <v-btn
          icon
          variant="text"
          @click="close"
        >
          <v-icon :icon="mdiClose" />
        </v-btn>
      </div>

      <v-card-text class="px-6 pt-4">
        <v-textarea
          v-model="input"
          variant="outlined"
          rounded="lg"
          rows="2"
          auto-grow
          autofocus
          hide-details
          :disabled="state === 'importing' || state === 'success'"
          placeholder="https://… or “Nonna's lasagna”"
          @drop.prevent="onDrop"
          @dragover.prevent
        />

        <!-- Detected source chip -->
        <div
          v-if="detectedUrl && state !== 'success'"
          class="mt-3"
        >
          <v-chip
            size="small"
            variant="tonal"
            color="accent"
          >
            <v-icon
              start
              size="small"
              :icon="mdiLinkVariant"
            />
            {{ domain }}
          </v-chip>
        </div>

        <!-- Scrape preview: loading shimmer -->
        <v-skeleton-loader
          v-if="state === 'previewLoading'"
          type="list-item-avatar-three-line"
          class="mt-4 rounded-lg"
        />

        <!-- Scrape preview: the recipe you're about to add -->
        <v-expand-transition>
          <div
            v-if="state === 'preview' && preview"
            class="quick-add__preview mt-4"
          >
            <img
              v-if="previewImage"
              :src="previewImage"
              class="quick-add__preview-img"
              alt=""
              @error="previewImage = null"
            >
            <div class="pa-4">
              <div class="quick-add__preview-title">
                {{ preview.name }}
              </div>
              <div
                v-if="preview.description"
                class="quick-add__preview-desc mt-1"
              >
                {{ preview.description }}
              </div>
              <div class="d-flex flex-wrap ga-2 mt-3">
                <v-chip
                  v-if="preview.totalTime"
                  size="x-small"
                  variant="tonal"
                  color="secondary"
                >
                  {{ humanizeTime(preview.totalTime) }}
                </v-chip>
                <v-chip
                  size="x-small"
                  variant="tonal"
                >
                  {{ domain }}
                </v-chip>
              </div>
            </div>
          </div>
        </v-expand-transition>

        <!-- Scrape preview failed -->
        <v-alert
          v-if="state === 'previewError'"
          type="warning"
          variant="tonal"
          density="comfortable"
          class="mt-4"
        >
          Couldn't read that site — you can still try importing it directly.
        </v-alert>

        <!-- Import in progress (live messages from the server) -->
        <div
          v-if="state === 'importing'"
          class="quick-add__progress d-flex align-center mt-4"
        >
          <v-progress-circular
            indeterminate
            size="22"
            width="2"
            color="primary"
            class="mr-3"
          />
          <span class="text-body-2">{{ progressMessage }}</span>
        </div>

        <!-- Success beat -->
        <div
          v-if="state === 'success'"
          class="quick-add__success d-flex align-center mt-4"
        >
          <v-icon
            :icon="mdiCheckCircle"
            color="success"
            size="28"
            class="mr-2 quick-add__success-icon"
          />
          <span class="text-body-1">Added to your collection — taking you there…</span>
        </div>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          density="comfortable"
          class="mt-4"
        >
          {{ errorMessage }}
        </v-alert>
      </v-card-text>

      <v-card-actions class="px-6 pb-6 pt-0">
        <v-btn
          v-if="showImageImport"
          variant="text"
          size="small"
          :to="`/g/${groupSlug}/r/create/image`"
          @click="close"
        >
          From images
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="primaryAction"
          color="primary"
          variant="flat"
          size="large"
          rounded="lg"
          :loading="state === 'importing'"
          :disabled="state === 'success'"
          @click="primaryAction.handler"
        >
          {{ primaryAction.label }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { watchDebounced } from "@vueuse/core";
import { mdiClose, mdiCheckCircle, mdiLinkVariant } from "@mdi/js";
import { useUserApi } from "~/composables/api";
import { useGroupSelf } from "~/composables/use-groups";
import { uuid4 } from "~/composables/use-utils";
import type { Recipe, RecipeIngredient, RecipeStep } from "~/lib/api/types/recipe";

type QuickAddState = "idle" | "previewLoading" | "preview" | "previewError" | "importing" | "success";

const dialog = defineModel<boolean>({ default: false });

const api = useUserApi();
const router = useRouter();
const route = useRoute();
const auth = useMealieAuth();
const { group } = useGroupSelf();

const groupSlug = computed(() => route.params.groupSlug as string || auth.user.value?.groupSlug || "");
const showImageImport = computed(() => group.value?.aiProviderSettings?.imageProviderEnabled);

const input = ref("");
const state = ref<QuickAddState>("idle");
const preview = ref<Recipe | null>(null);
const previewImage = ref<string | null>(null);
const progressMessage = ref("Contacting the site…");
const errorMessage = ref("");
let lastTestedUrl = "";

const URL_REGEX = /(https?:\/\/[^\s<>"']+)/i;

const detectedUrl = computed(() => {
  const match = input.value.match(URL_REGEX);
  return match ? match[1] : null;
});

const domain = computed(() => {
  if (!detectedUrl.value) {
    return "";
  }
  try {
    return new URL(detectedUrl.value).hostname.replace(/^www\./, "");
  }
  catch {
    return "";
  }
});

const looksLikeMarkup = computed(() => {
  const text = input.value.trim();
  return !detectedUrl.value && (text.startsWith("{") || text.startsWith("<"));
});

const firstLine = computed(() => {
  const line = input.value.trim().split("\n")[0] || "";
  return line.length > 40 ? `${line.slice(0, 40)}…` : line;
});

// Scrape previews return raw ISO-8601 durations (e.g. "PT1H20M"); Mealie
// normalizes these on real import, but humanize for the preview chip.
function humanizeTime(t: string | null) {
  if (!t) {
    return "";
  }
  const m = /^PT(?:(\d+)H)?(?:(\d+)M)?$/i.exec(t.trim());
  if (!m) {
    return t;
  }
  const parts: string[] = [];
  if (m[1]) {
    parts.push(`${m[1]} hr`);
  }
  if (m[2]) {
    parts.push(`${m[2]} min`);
  }
  return parts.join(" ") || t;
}

const nonEmptyLines = computed(() => input.value.split("\n").map(l => l.trim()).filter(Boolean));

// Multi-line / substantial free text = a recipe to parse, not just a name.
const isRecipeText = computed(() =>
  !detectedUrl.value && !looksLikeMarkup.value
  && (nonEmptyLines.value.length > 1 || input.value.trim().length > 60),
);

const primaryAction = computed(() => {
  if (!input.value.trim() || state.value === "success") {
    return null;
  }
  if (detectedUrl.value) {
    return {
      label: state.value === "previewError" ? "Import anyway" : "Add to collection",
      handler: importFromUrl,
    };
  }
  if (looksLikeMarkup.value) {
    return { label: "Parse & import", handler: importFromMarkup };
  }
  if (isRecipeText.value) {
    return { label: "Parse & add recipe", handler: parseTextToRecipe };
  }
  return { label: `Create “${firstLine.value}”`, handler: createFromScratch };
});

// Live scrape preview as soon as a URL is detected
watchDebounced(
  input,
  async () => {
    if (state.value === "importing" || state.value === "success") {
      return;
    }
    errorMessage.value = "";

    const url = detectedUrl.value;
    if (!url) {
      state.value = "idle";
      preview.value = null;
      lastTestedUrl = "";
      return;
    }
    if (url === lastTestedUrl) {
      return;
    }

    lastTestedUrl = url;
    state.value = "previewLoading";
    preview.value = null;
    previewImage.value = null;

    const { data } = await api.recipes.testCreateOneUrl(url);

    // The input may have changed while we were fetching
    if (detectedUrl.value !== url || state.value !== "previewLoading") {
      return;
    }

    if (data?.name) {
      preview.value = data;
      previewImage.value
        = typeof data.image === "string" && /^https?:\/\//.test(data.image) ? data.image : null;
      state.value = "preview";
    }
    else {
      state.value = "previewError";
    }
  },
  { debounce: 450 },
);

async function importFromUrl() {
  if (!detectedUrl.value) {
    return;
  }
  errorMessage.value = "";
  state.value = "importing";
  progressMessage.value = "Contacting the site…";

  const { data: slug, error } = await api.recipes.createOneByUrl(
    detectedUrl.value,
    true,
    true,
    message => (progressMessage.value = message),
  );

  if (error || !slug) {
    state.value = "previewError";
    errorMessage.value = "That import didn't work. Try pasting the recipe text instead.";
    return;
  }
  await celebrateAndGo(slug);
}

async function importFromMarkup() {
  errorMessage.value = "";
  state.value = "importing";
  progressMessage.value = "Parsing your recipe…";

  const { data: slug, error } = await api.recipes.createOneByHtmlOrJson(
    input.value,
    true,
    true,
    null,
    message => (progressMessage.value = message),
  );

  if (error || !slug) {
    state.value = "idle";
    errorMessage.value = "Couldn't find a recipe in that text.";
    return;
  }
  await celebrateAndGo(slug);
}

// ── Free-text recipe parsing (no AI required) ─────────────────────────────
// Walks pasted text section-by-section: content before the first recognized
// header is the description; headers switch the active section; sections end
// at the next header. Falls back to per-line heuristics when no headers exist.
const ING_HEADER = /^(ingredients?)\b\s*:?\s*$/i;
const INST_HEADER = /^(instructions?|directions?|method|steps?|preparation)\b\s*:?\s*$/i;
const NOTE_HEADER = /^(notes?|tips?|nutrition|health\s*notes?)\b\s*:?\s*$/i;
const MEASURE = /\b(cups?|tbsp|tablespoons?|tsp|teaspoons?|oz|ounces?|lbs?|pounds?|g|grams?|kg|ml|l|cloves?|pinch|cans?|sticks?|packets?|packages?|slices?|sprigs?)\b/i;

type Section = "description" | "ingredients" | "instructions" | "notes";

interface SegmentedRecipe {
  title: string;
  description: string;
  ingredients: string[];
  instructions: string[];
  notes: string;
}

function looksLikeIngredient(line: string): boolean {
  if (line.length > 160) {
    return false;
  }
  return /^(\d|½|¼|¾|⅓|⅔|⅛|⅜|⅝|⅞|a |an |one |two |three |four )/i.test(line) || MEASURE.test(line);
}

function stripIngredientBullet(line: string): string {
  return line.replace(/^\s*[-*•·]\s*/, "").trim();
}

function stripStepBullet(line: string): string {
  return line.replace(/^\s*(\d+\s*[.)]\s*|step\s*\d+\s*[:.)]?\s*|[-*•·]\s*)/i, "").trim();
}

function joinParagraphs(lines: string[]): string {
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function segmentRecipeText(raw: string): SegmentedRecipe {
  const lines = raw.split("\n").map(l => l.trim());

  let i = 0;
  while (i < lines.length && !lines[i]) {
    i++;
  }
  const title = (lines[i] || "New Recipe").replace(/^#+\s*/, "");
  i++;

  const buckets: Record<Section, string[]> = { description: [], ingredients: [], instructions: [], notes: [] };
  let current: Section = "description";
  for (; i < lines.length; i++) {
    const l = lines[i];
    if (ING_HEADER.test(l)) {
      current = "ingredients";
      continue;
    }
    if (INST_HEADER.test(l)) {
      current = "instructions";
      continue;
    }
    if (NOTE_HEADER.test(l)) {
      current = "notes";
      continue;
    }
    buckets[current].push(l);
  }

  const ingredients = buckets.ingredients.map(stripIngredientBullet).filter(Boolean);
  const instructions = buckets.instructions.map(stripStepBullet).filter(Boolean);

  // No section headers found — classify the leading block line by line.
  if (!ingredients.length && !instructions.length) {
    for (const l of buckets.description.filter(Boolean)) {
      if (looksLikeIngredient(l)) {
        ingredients.push(stripIngredientBullet(l));
      }
      else {
        instructions.push(stripStepBullet(l));
      }
    }
    buckets.description = [];
  }

  return {
    title: title || "New Recipe",
    description: joinParagraphs(buckets.description),
    ingredients,
    instructions,
    notes: joinParagraphs(buckets.notes),
  };
}

async function parseTextToRecipe() {
  errorMessage.value = "";
  state.value = "importing";
  progressMessage.value = "Reading your recipe…";

  const segmented = segmentRecipeText(input.value);

  const { data: created, error } = await api.recipes.createOne({ name: segmented.title });
  if (error || !created) {
    state.value = "idle";
    errorMessage.value = "Couldn't create the recipe. Maybe that name is already taken?";
    return;
  }
  const slug = typeof created === "string" ? created : ((created as Recipe).slug || "");

  const { data: recipe } = await api.recipes.getOne(slug);
  if (!recipe) {
    // Recipe exists but we couldn't reload it; still route there.
    await celebrateAndGo(slug);
    return;
  }

  progressMessage.value = "Adding ingredients & steps…";

  if (segmented.description) {
    recipe.description = segmented.description;
  }
  // Store ingredient lines as their original text — exactly how Mealie stores
  // unparsed imports. Users can structure them later via "Parse Ingredients".
  recipe.recipeIngredient = segmented.ingredients.map<RecipeIngredient>(line => ({
    referenceId: uuid4(),
    quantity: null,
    unit: null,
    food: null,
    note: line,
    originalText: line,
    title: null,
  }));
  recipe.recipeInstructions = segmented.instructions.map<RecipeStep>(text => ({
    id: uuid4(),
    title: "",
    text,
  }));
  if (segmented.notes) {
    recipe.notes = [{ title: "Notes", text: segmented.notes }];
  }

  await api.recipes.updateOne(slug, recipe);
  await celebrateAndGo(slug);
}

async function createFromScratch() {
  errorMessage.value = "";
  state.value = "importing";
  progressMessage.value = "Creating your recipe…";

  const { data, error } = await api.recipes.createOne({ name: input.value.trim().split("\n")[0] });

  if (error || !data) {
    state.value = "idle";
    errorMessage.value = "Couldn't create that recipe. Maybe the name is already taken?";
    return;
  }
  await celebrateAndGo(typeof data === "string" ? data : (data as Recipe).slug || "");
}

async function celebrateAndGo(slug: string) {
  state.value = "success";
  setTimeout(() => {
    router.push(`/g/${groupSlug.value}/r/${slug}`);
    close();
  }, 750);
}

function onDrop(event: DragEvent) {
  const text = event.dataTransfer?.getData("text");
  if (text) {
    input.value = text;
  }
}

function onDialogToggle(open: boolean) {
  if (!open) {
    reset();
  }
}

function close() {
  dialog.value = false;
  setTimeout(reset, 300);
}

function reset() {
  input.value = "";
  state.value = "idle";
  preview.value = null;
  previewImage.value = null;
  errorMessage.value = "";
  lastTestedUrl = "";
}
</script>

<style scoped>
.quick-add__muted {
  opacity: 0.6;
}

.quick-add__preview {
  overflow: hidden;
  border: 1px solid rgba(var(--v-border-color), 0.12);
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
  animation: quick-add-rise 0.25s ease;
}

.quick-add__preview-img {
  display: block;
  width: 100%;
  height: 180px;
  object-fit: cover;
}

.quick-add__preview-title {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.25;
}

.quick-add__preview-desc {
  font-size: 0.85rem;
  line-height: 1.4;
  opacity: 0.6;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
}

.quick-add__success-icon {
  animation: quick-add-pop 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.4);
}

@keyframes quick-add-rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes quick-add-pop {
  from {
    transform: scale(0.4);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
