<template>
  <div
    class="editor-bar d-print-none"
    :class="lgAndUp ? 'editor-bar--top' : 'editor-bar--bottom'"
  >
    <BaseDialog
      v-model="deleteDialog"
      :title="$t('recipe.delete-recipe')"
      :icon="mdiAlertCircle"
      color="error"
      can-delete
      @delete="$emit('delete')"
    >
      <v-card-text>
        {{ $t("recipe.delete-confirmation") }}
      </v-card-text>
    </BaseDialog>

    <div class="editor-bar__inner d-flex align-center px-4">
      <div
        v-if="lgAndUp"
        class="editor-bar__title-block d-flex align-center mr-4"
      >
        <div class="mr-3">
          <div class="editor-bar__overline">
            Editing
          </div>
          <div class="editor-bar__name">
            {{ name }}
          </div>
        </div>
        <div
          v-if="dirty && saveState === 'idle'"
          v-tooltip="'Unsaved changes'"
          class="editor-bar__dirty-dot"
        >
          <span class="d-sr-only">Unsaved changes</span>
        </div>
      </div>

      <v-spacer />

      <v-btn
        v-if="!isJsonMode"
        icon
        variant="text"
        density="comfortable"
        class="mr-1"
        @click="$emit('open-settings')"
      >
        <v-icon :icon="mdiCog" />
      </v-btn>

      <v-menu offset-y>
        <template #activator="{ props: menuProps }">
          <v-btn
            icon
            variant="text"
            density="comfortable"
            class="mr-1"
            v-bind="menuProps"
          >
            <v-icon :icon="mdiDotsVertical" />
          </v-btn>
        </template>
        <v-list density="comfortable">
          <v-list-item @click="$emit('toggle-json')">
            <template #prepend>
              <v-icon :icon="mdiCodeBraces" />
            </template>
            <v-list-item-title>{{ isJsonMode ? "Edit as form" : "Edit as JSON" }}</v-list-item-title>
          </v-list-item>
          <v-divider class="my-1" />
          <v-list-item @click="deleteDialog = true">
            <template #prepend>
              <v-icon
                :icon="mdiDelete"
                color="error"
              />
            </template>
            <v-list-item-title class="text-error">
              {{ $t("recipe.delete-recipe") }}
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>

      <v-btn
        variant="text"
        class="mr-2"
        @click="$emit('close')"
      >
        {{ $t("general.cancel") }}
      </v-btn>

      <v-btn
        v-tooltip="saveTooltip"
        color="primary"
        variant="flat"
        rounded="lg"
        class="editor-bar__save"
        :class="{ 'editor-bar__save--error': saveState === 'error', 'flex-grow-1': !lgAndUp }"
        @click="$emit('save')"
      >
        <Transition
          name="save-swap"
          mode="out-in"
        >
          <span
            v-if="saveState === 'saving'"
            key="saving"
            class="d-flex align-center"
          >
            <v-progress-circular
              indeterminate
              size="16"
              width="2"
              class="mr-2"
            />
            Saving…
          </span>
          <span
            v-else-if="saveState === 'success'"
            key="success"
            class="d-flex align-center"
          >
            <v-icon
              :icon="mdiCheck"
              class="editor-bar__save-check mr-1"
              size="18"
            />
            Saved
          </span>
          <span
            v-else
            key="idle"
          >{{ $t("general.save") }}</span>
        </Transition>
      </v-btn>

      <span
        class="d-sr-only"
        aria-live="polite"
      >{{ liveText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { mdiAlertCircle, mdiCheck, mdiCodeBraces, mdiCog, mdiDelete, mdiDotsVertical } from "@mdi/js";
import type { SaveState } from "~/composables/recipe-page/shared-state";

const props = defineProps<{
  name: string;
  dirty: boolean;
  saveState: SaveState;
  isJsonMode: boolean;
}>();

defineEmits<{
  "save": [];
  "close": [];
  "delete": [];
  "toggle-json": [];
  "open-settings": [];
}>();

const display = useDisplay();
const lgAndUp = display.lgAndUp;

const deleteDialog = ref(false);

const isMac = computed(() => /mac/i.test(navigator.platform ?? ""));
const saveTooltip = computed(() => (isMac.value ? "Save (⌘S)" : "Save (Ctrl+S)"));

const liveText = computed(() => {
  switch (props.saveState) {
    case "saving":
      return "Saving";
    case "success":
      return "Saved";
    case "error":
      return "Save failed";
    default:
      return "";
  }
});
</script>

<style scoped>
.editor-bar {
  z-index: 6;
  animation: editor-bar-drop 0.2s ease;
}

.editor-bar--top {
  position: sticky;
  top: 68px;
  background: rgba(var(--v-theme-background), 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(var(--v-border-color), 0.1);
}

.editor-bar--bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2012;
  background: rgb(var(--v-theme-surface));
  border-top: 1px solid rgba(var(--v-border-color), 0.12);
  box-shadow: 0 -2px 12px rgba(43, 37, 33, 0.06);
  padding-bottom: env(safe-area-inset-bottom);
}

.editor-bar__inner {
  min-height: 60px;
}

.editor-bar__overline {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.55;
  line-height: 1.1;
}

.editor-bar__name {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 1.1rem;
  line-height: 1.2;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.editor-bar__dirty-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  animation: ms-pop var(--ms-dur-base) var(--ms-ease-spring);
}

.editor-bar__save {
  min-width: 116px;
}

.editor-bar__save--error {
  animation: ms-shake 0.4s var(--ms-ease);
}

.editor-bar__save-check {
  animation: ms-pop 0.35s var(--ms-ease-spring);
}

.save-swap-enter-active,
.save-swap-leave-active {
  transition: opacity var(--ms-dur-fast) var(--ms-ease);
}

.save-swap-enter-from,
.save-swap-leave-to {
  opacity: 0;
}

@keyframes editor-bar-drop {
  from {
    opacity: 0;
    transform: translateY(-12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
