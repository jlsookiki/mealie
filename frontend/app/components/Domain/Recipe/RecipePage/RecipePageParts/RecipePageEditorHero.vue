<template>
  <div class="recipe-hero">
    <!-- Remove confirmation -->
    <BaseDialog
      v-model="deleteDialog"
      :title="$t('recipe.delete-image')"
      :icon="mdiAlertCircle"
      color="error"
      can-delete
      @delete="removeImage"
    >
      <v-card-text>
        {{ $t("recipe.delete-image-confirmation") }}
      </v-card-text>
    </BaseDialog>

    <!-- Crop dialog -->
    <v-dialog
      v-model="cropDialog"
      max-width="700"
      :fullscreen="$vuetify.display.xs"
    >
      <v-card
        rounded="xl"
        class="pa-4"
      >
        <div class="d-flex align-center mb-3">
          <h2 class="text-h5">
            Crop photo
          </h2>
          <v-spacer />
          <v-btn
            icon
            variant="text"
            @click="cropDialog = false"
          >
            <v-icon :icon="mdiClose" />
          </v-btn>
        </div>
        <ImageCropper
          v-if="cropDialog"
          :img="imageUrl"
          cropper-height="420px"
          cropper-width="100%"
          @save="onCropSave"
        />
      </v-card>
    </v-dialog>

    <DropZone
      class="recipe-hero__zone"
      @drop="onDropFiles"
    >
      <!-- Image present -->
      <div
        v-if="hasImage"
        class="recipe-hero__media-wrap"
        :class="{ 'recipe-hero__media-wrap--uploading': uploading }"
      >
        <Transition name="hero-fade">
          <v-img
            :key="imageKey"
            class="recipe-hero__media"
            :src="imageUrl"
            cover
            :height="$vuetify.display.xs ? 200 : 320"
            @error="imageFailed = true"
          />
        </Transition>
        <v-progress-linear
          v-if="uploading"
          indeterminate
          color="primary"
          height="2"
          class="recipe-hero__progress"
        />

        <!-- Overlay actions -->
        <div class="recipe-hero__actions">
          <AppButtonUpload
            url="none"
            file-name="image"
            accept="image/*"
            :post="false"
            @uploaded="uploadImage"
          >
            <template #default="{ onButtonClick }">
              <v-btn
                size="small"
                variant="elevated"
                rounded="lg"
                class="recipe-hero__action"
                @click="onButtonClick"
              >
                <v-icon
                  start
                  :icon="mdiUpload"
                />
                Replace
              </v-btn>
            </template>
          </AppButtonUpload>
          <v-btn
            size="small"
            variant="elevated"
            rounded="lg"
            class="recipe-hero__action"
            @click="urlOpen = !urlOpen"
          >
            <v-icon
              start
              :icon="mdiLinkVariant"
            />
            URL
          </v-btn>
          <v-btn
            size="small"
            variant="elevated"
            rounded="lg"
            class="recipe-hero__action"
            @click="cropDialog = true"
          >
            <v-icon
              start
              :icon="mdiCropFree"
            />
            Crop
          </v-btn>
          <v-btn
            size="small"
            variant="elevated"
            rounded="lg"
            class="recipe-hero__action recipe-hero__action--danger"
            @click="deleteDialog = true"
          >
            <v-icon
              start
              :icon="mdiDelete"
            />
            Remove
          </v-btn>
        </div>
      </div>

      <!-- Empty state -->
      <AppButtonUpload
        v-else
        url="none"
        file-name="image"
        accept="image/*"
        :post="false"
        @uploaded="uploadImage"
      >
        <template #default="{ onButtonClick }">
          <div
            class="recipe-hero__empty d-flex flex-column align-center justify-center"
            role="button"
            tabindex="0"
            @click="onButtonClick"
            @keydown.enter.prevent="onButtonClick"
          >
            <v-icon
              :icon="mdiImagePlus"
              size="44"
              color="primary"
              class="mb-2 recipe-hero__empty-icon"
            />
            <div class="recipe-hero__empty-title">
              Add a cover photo
            </div>
            <div class="recipe-hero__empty-hint">
              Drag &amp; drop, click to upload, or paste a URL below
            </div>
            <div class="d-flex ga-2 mt-3">
              <v-btn
                size="small"
                variant="tonal"
                color="accent"
                rounded="lg"
                @click.stop="urlOpen = !urlOpen"
              >
                <v-icon
                  start
                  :icon="mdiLinkVariant"
                />
                From URL
              </v-btn>
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                rounded="lg"
                :loading="generating"
                @click.stop="generateImage"
              >
                <v-icon
                  start
                  :icon="mdiCreation"
                />
                Generate
              </v-btn>
            </div>
          </div>
        </template>
      </AppButtonUpload>
    </DropZone>

    <!-- URL import row -->
    <v-expand-transition>
      <div
        v-if="urlOpen"
        class="d-flex align-center ga-2 mt-2"
      >
        <v-text-field
          v-model="url"
          autofocus
          hide-details
          density="compact"
          variant="outlined"
          rounded="lg"
          placeholder="https://example.com/photo.jpg"
          @keydown.enter.prevent="importFromUrl"
        />
        <v-btn
          color="primary"
          variant="tonal"
          rounded="lg"
          :loading="uploading"
          :disabled="!url"
          @click="importFromUrl"
        >
          {{ $t("general.get") }}
        </v-btn>
      </div>
    </v-expand-transition>
  </div>
</template>

<script setup lang="ts">
import {
  mdiAlertCircle,
  mdiClose,
  mdiCreation,
  mdiCropFree,
  mdiDelete,
  mdiImagePlus,
  mdiLinkVariant,
  mdiUpload,
} from "@mdi/js";
import { usePageState } from "~/composables/recipe-page/shared-state";
import { useStaticRoutes, useUserApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import type { Recipe } from "~/lib/api/types/recipe";

const recipe = defineModel<NoUndefinedField<Recipe>>({ required: true });
const emit = defineEmits<{ "image-updated": [] }>();

const api = useUserApi();
const { recipeImage } = useStaticRoutes();
const { imageKey } = usePageState(recipe.value.slug);

const uploading = ref(false);
const generating = ref(false);
const urlOpen = ref(false);
const url = ref("");
const cropDialog = ref(false);
const deleteDialog = ref(false);
const imageFailed = ref(false);

const hasImage = computed(() => !!recipe.value.image && !imageFailed.value);
const imageUrl = computed(() => recipeImage(recipe.value.id, recipe.value.image, imageKey.value));

async function uploadImage(fileObject: File | File[]) {
  const file = Array.isArray(fileObject) ? fileObject[0] : fileObject;
  if (!file || !recipe.value.slug) {
    return;
  }
  uploading.value = true;
  try {
    const { data } = await api.recipes.updateImage(recipe.value.slug, file);
    if (data?.image) {
      recipe.value.image = data.image;
    }
    imageFailed.value = false;
    imageKey.value++;
    emit("image-updated");
  }
  finally {
    uploading.value = false;
  }
}

async function importFromUrl() {
  if (!url.value || !recipe.value.slug) {
    return;
  }
  uploading.value = true;
  try {
    const { data, error } = await api.recipes.updateImagebyURL(recipe.value.slug, url.value);
    if (error) {
      alert.error("Couldn't fetch an image from that URL.");
      return;
    }
    if (data?.image) {
      recipe.value.image = data.image;
    }
    imageFailed.value = false;
    imageKey.value++;
    urlOpen.value = false;
    url.value = "";
    emit("image-updated");
  }
  finally {
    uploading.value = false;
  }
}

async function onCropSave(blob: Blob) {
  cropDialog.value = false;
  // updateImage derives the extension from the file name, so wrap the blob.
  const file = new File([blob], "cropped.png", { type: blob.type || "image/png" });
  await uploadImage(file);
}

async function removeImage() {
  if (!recipe.value.slug) {
    return;
  }
  await api.recipes.deleteImage(recipe.value.slug);
  recipe.value.image = "";
  imageFailed.value = false;
  imageKey.value++;
  emit("image-updated");
}

function onDropFiles(files: File[]) {
  const image = files.find(f => f.type.startsWith("image/"));
  if (image) {
    uploadImage(image);
  }
}

async function generateImage() {
  if (!recipe.value.slug || generating.value) {
    return;
  }
  generating.value = true;
  try {
    const { data, error } = await api.recipes.generateImage(recipe.value.slug);
    if (error || !data) {
      alert.error("Couldn't generate a photo — is an image provider configured?");
      return;
    }
    recipe.value.image = data.image;
    imageFailed.value = false;
    imageKey.value++;
    emit("image-updated");
    alert.success("Cover photo generated");
  }
  finally {
    generating.value = false;
  }
}
</script>

<style scoped>
.recipe-hero__zone {
  border-radius: var(--ms-radius-xl);
}

.recipe-hero__media-wrap {
  position: relative;
  overflow: hidden;
  border-radius: var(--ms-radius-xl);
  box-shadow: var(--ms-shadow-sm);
}

.recipe-hero__media {
  transition: transform var(--ms-dur-base) var(--ms-ease);
}

.recipe-hero__zone:deep(.drop-zone--over) .recipe-hero__media,
.drop-zone--over .recipe-hero__media {
  transform: scale(1.01);
}

/* Upload shimmer sweep */
.recipe-hero__media-wrap--uploading::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.25), transparent);
  animation: ms-sweep 1.2s linear infinite;
  pointer-events: none;
}

.recipe-hero__progress {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
}

.recipe-hero__actions {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
  opacity: 0;
  transition: opacity var(--ms-dur-fast) var(--ms-ease);
}

.recipe-hero__media-wrap:hover .recipe-hero__actions,
.recipe-hero__media-wrap:focus-within .recipe-hero__actions {
  opacity: 1;
}

@media (hover: none) {
  .recipe-hero__actions {
    opacity: 1;
  }
}

.recipe-hero__action {
  background: rgba(var(--v-theme-surface), 0.92) !important;
  backdrop-filter: blur(4px);
}

.recipe-hero__action--danger {
  color: rgb(var(--v-theme-error)) !important;
}

/* Empty state */
.recipe-hero__empty {
  min-height: 220px;
  border: 2px dashed rgba(var(--v-theme-primary), 0.4);
  border-radius: var(--ms-radius-xl);
  background: rgba(var(--v-theme-primary), 0.02);
  cursor: pointer;
  transition:
    border-color 0.2s var(--ms-ease),
    background 0.2s var(--ms-ease);
}

.recipe-hero__empty:hover,
.recipe-hero__empty:focus-visible {
  border-color: rgba(var(--v-theme-primary), 0.8);
  background: rgba(var(--v-theme-primary), 0.04);
  outline: none;
}

.recipe-hero__empty:hover .recipe-hero__empty-icon {
  transform: translateY(-2px);
}

.recipe-hero__empty-icon {
  transition: transform 0.2s var(--ms-ease);
}

.recipe-hero__empty-title {
  font-family: var(--font-display);
  font-size: 1.3rem;
  font-weight: 600;
}

.recipe-hero__empty-hint {
  font-size: 0.85rem;
  opacity: 0.6;
}

/* Image crossfade */
.hero-fade-enter-active,
.hero-fade-leave-active {
  transition: opacity var(--ms-dur-slow) var(--ms-ease);
}

.hero-fade-enter-from,
.hero-fade-leave-to {
  opacity: 0;
}

.hero-fade-leave-active {
  position: absolute;
  inset: 0;
}
</style>
