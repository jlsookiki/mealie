import type { MaybeRefOrGetter } from "vue";

/**
 * Binds Cmd/Ctrl+S to a save handler while `enabled` is truthy.
 * Outside the enabled state the event falls through to the browser.
 */
export function useSaveShortcut(handler: () => void, enabled: MaybeRefOrGetter<boolean>) {
  function onKeydown(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "s") {
      if (!toValue(enabled)) {
        return;
      }
      e.preventDefault();
      handler();
    }
  }

  onMounted(() => document.addEventListener("keydown", onKeydown));
  onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));
}
