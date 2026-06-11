<template>
  <v-dialog
    v-model="dialog"
    max-width="520"
    :fullscreen="$vuetify.display.xs"
  >
    <v-card
      rounded="xl"
      class="share-sheet"
    >
      <div class="d-flex align-center px-6 pt-5 pb-1">
        <h2 class="text-h5">
          {{ $t("recipe-share.share-recipe") }}
        </h2>
        <v-spacer />
        <v-btn
          icon
          variant="text"
          @click="dialog = false"
        >
          <v-icon :icon="mdiClose" />
        </v-btn>
      </div>

      <!-- The unfurl card: exactly what the recipient's messenger will render -->
      <div class="px-6 pt-3">
        <div class="share-sheet__preview">
          <img
            v-if="!imageFailed"
            :src="imageUrl"
            class="share-sheet__img"
            alt=""
            @error="imageFailed = true"
          >
          <div
            v-else
            class="share-sheet__img share-sheet__img--fallback d-flex align-center justify-center"
          >
            <v-icon
              size="56"
              color="primary"
            >
              {{ $globals.icons.primary }}
            </v-icon>
          </div>
          <div class="pa-4">
            <div class="share-sheet__title">
              {{ name }}
            </div>
            <div class="share-sheet__host mt-1">
              {{ host }}
            </div>
          </div>
        </div>
        <p class="share-sheet__caption text-center mt-3 mb-0">
          This is the preview card they'll see.
        </p>
      </div>

      <div class="px-6 pt-4 pb-2 d-flex flex-column ga-2">
        <v-btn
          block
          size="large"
          color="primary"
          variant="flat"
          rounded="lg"
          :loading="preparing"
          @click="doShare"
        >
          <v-icon
            start
            :icon="mdiShareVariant"
          />
          Share
        </v-btn>
        <v-btn
          block
          size="large"
          color="accent"
          variant="tonal"
          rounded="lg"
          :loading="preparing"
          @click="doCopy"
        >
          <v-icon
            start
            :icon="copied ? mdiCheck : mdiContentCopy"
          />
          {{ copied ? "Copied!" : "Copy link" }}
        </v-btn>
      </div>

      <!-- Advanced: manage share links -->
      <v-expansion-panels
        flat
        class="px-3 pb-4"
      >
        <v-expansion-panel
          elevation="0"
          rounded="lg"
        >
          <v-expansion-panel-title class="text-body-2">
            Manage share links
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-menu
              v-model="datePickerMenu"
              :close-on-content-click="false"
              transition="scale-transition"
              offset-y
              max-width="290px"
              min-width="auto"
            >
              <template #activator="{ props: activatorProps }">
                <v-text-field
                  :model-value="$d(expirationDate)"
                  :label="$t('recipe-share.expiration-date')"
                  :hint="$t('recipe-share.default-30-days')"
                  persistent-hint
                  density="comfortable"
                  :prepend-icon="$globals.icons.calendar"
                  v-bind="activatorProps"
                  readonly
                />
              </template>
              <v-date-picker
                v-model="expirationDate"
                hide-header
                :first-day-of-week="firstDayOfWeek"
                :local="$i18n.locale"
                @update:model-value="datePickerMenu = false"
              />
            </v-menu>
            <div class="d-flex justify-end mt-2">
              <BaseButton
                size="small"
                @click="createNewToken"
              >
                {{ $t("general.new") }}
              </BaseButton>
            </div>

            <v-list-item
              v-for="token in tokens"
              :key="token.id"
              class="px-2 mt-1"
              rounded="lg"
              @click="shareToken(token.id)"
            >
              <div
                class="d-flex align-center"
                style="width: 100%;"
              >
                <v-icon
                  color="accent"
                  class="mr-3"
                >
                  {{ $globals.icons.link }}
                </v-icon>
                <div class="flex-grow-1">
                  <v-list-item-title class="text-body-2">
                    {{ $t("recipe-share.expires-at") + ' ' + $d(new Date(token.expiresAt!), "short") }}
                  </v-list-item-title>
                </div>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  @click.stop="deleteToken(token.id)"
                >
                  <v-icon color="error-lighten-1">
                    {{ $globals.icons.delete }}
                  </v-icon>
                </v-btn>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  @click.stop="copyTokenLink(token.id)"
                >
                  <v-icon color="info-lighten-1">
                    {{ $globals.icons.contentCopy }}
                  </v-icon>
                </v-btn>
              </div>
            </v-list-item>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { useClipboard, useShare, whenever } from "@vueuse/core";
import { mdiClose, mdiShareVariant, mdiContentCopy, mdiCheck } from "@mdi/js";
import type { RecipeShareToken } from "~/lib/api/types/recipe";
import { useUserApi, useStaticRoutes } from "~/composables/api";
import { useHouseholdSelf } from "~/composables/use-households";
import { alert } from "~/composables/use-toast";

interface Props {
  recipeId: string;
  name: string;
}
const props = defineProps<Props>();

const dialog = defineModel<boolean>({ default: false });

const datePickerMenu = ref(false);
const expirationDate = ref(new Date(Date.now() - new Date().getTimezoneOffset() * 60000));
const tokens = ref<RecipeShareToken[]>([]);
const preparing = ref(false);
const imageFailed = ref(false);

const { recipeImage } = useStaticRoutes();
const imageUrl = computed(() => recipeImage(props.recipeId));
const host = computed(() => window.location.host);

whenever(
  () => dialog.value,
  async () => {
    // Set expiration date to today + 30 Days
    const today = new Date();
    expirationDate.value = new Date(today.getTime() + 30 * 24 * 60 * 60 * 1000);
    imageFailed.value = false;

    // Have a link ready the moment the sheet opens
    preparing.value = true;
    await refreshTokens();
    if (tokens.value.length === 0) {
      await createNewToken();
    }
    preparing.value = false;
  },
);

const i18n = useI18n();
const auth = useMealieAuth();
const { household } = useHouseholdSelf();
const route = useRoute();
const groupSlug = computed(() => route.params.groupSlug as string || auth.user.value?.groupSlug || "");

const firstDayOfWeek = computed(() => {
  return household.value?.preferences?.firstDayOfWeek || 0;
});

// ============================================================
// Token Actions

const userApi = useUserApi();

async function createNewToken() {
  const { data } = await userApi.recipes.share.createOne({
    recipeId: props.recipeId,
    expiresAt: expirationDate.value.toISOString(),
  });

  if (data) {
    tokens.value.push(data);
  }
}

async function deleteToken(id: string) {
  await userApi.recipes.share.deleteOne(id);
  tokens.value = tokens.value.filter(token => token.id !== id);
}

async function refreshTokens() {
  const { data } = await userApi.recipes.share.getAll(1, -1, { recipe_id: props.recipeId });

  if (data) {
    // @ts-expect-error - TODO: This routes doesn't have pagination, but the type are mismatched.
    tokens.value = data ?? [];
  }
}

const { share, isSupported: shareIsSupported } = useShare();
const { copy, copied, isSupported: clipboardIsSupported } = useClipboard({ copiedDuring: 2000 });

function getRecipeText() {
  return i18n.t("recipe.share-recipe-message", [props.name]);
}

function getTokenLink(token: string) {
  return `${window.location.origin}/g/${groupSlug.value}/shared/r/${token}`;
}

async function copyTokenLink(token: string) {
  if (clipboardIsSupported.value) {
    await copy(getTokenLink(token));
    if (!copied.value) {
      alert.error(i18n.t("general.clipboard-copy-failure") as string);
    }
  }
  else {
    alert.error(i18n.t("general.clipboard-not-supported") as string);
  }
}

async function shareToken(token: string) {
  if (shareIsSupported.value) {
    share({
      title: props.name,
      url: getTokenLink(token),
      text: getRecipeText() as string,
    });
  }
  else {
    await copyTokenLink(token);
  }
}

async function doShare() {
  if (tokens.value.length === 0) {
    await createNewToken();
  }
  const token = tokens.value[0];
  if (token) {
    await shareToken(token.id);
  }
}

async function doCopy() {
  if (tokens.value.length === 0) {
    await createNewToken();
  }
  const token = tokens.value[0];
  if (token) {
    await copyTokenLink(token.id);
  }
}
</script>

<style scoped>
.share-sheet__preview {
  overflow: hidden;
  border: 1px solid rgba(var(--v-border-color), 0.12);
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
  box-shadow: var(--ms-shadow-sm);
}

.share-sheet__img {
  display: block;
  width: 100%;
  height: 200px;
  object-fit: cover;
}

.share-sheet__img--fallback {
  background: rgba(var(--v-theme-primary), 0.06);
}

.share-sheet__title {
  font-family: var(--font-display);
  font-size: 1.3rem;
  font-weight: 600;
  line-height: 1.25;
}

.share-sheet__host {
  font-size: 0.8rem;
  opacity: 0.55;
}

.share-sheet__caption {
  font-size: 0.8rem;
  opacity: 0.55;
}
</style>
