<template>
  <div
    ref="el"
    class="drop-zone"
    :class="{ 'drop-zone--over': isOverDropZone }"
  >
    <div
      v-if="isOverDropZone"
      class="drop-zone__overlay"
    >
      <p class="drop-zone__label">
        {{ $t("recipe.drop-image") }}
      </p>
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
import { useDropZone } from "@vueuse/core";

defineProps({
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["drop"]);

const el = ref<HTMLDivElement>();

function onDrop(files: File[] | null) {
  if (files) {
    emit("drop", files);
  }
}

const { isOverDropZone } = useDropZone(el, files => onDrop(files));
</script>

<style lang="css">
.drop-zone {
  position: relative;
}

.drop-zone__overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: inherit;
  background: rgba(var(--v-theme-primary), 0.08);
  border: 2px dashed rgba(var(--v-theme-primary), 0.8);
}

.drop-zone__label {
  margin: 0;
  background: rgb(var(--v-theme-surface));
  box-shadow: var(--ms-shadow-sm);
  border-radius: 999px;
  padding: 8px 20px;
  font-weight: 600;
  animation: ms-pop var(--ms-dur-base, 0.25s) var(--ms-ease-spring, ease);
}
</style>
