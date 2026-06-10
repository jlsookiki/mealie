<template>
  <nav class="app-bottom-nav d-print-none bg-surface">
    <NuxtLink
      v-for="link in links"
      :key="link.title"
      :to="link.to"
      class="app-bottom-nav__item"
      :class="{ 'app-bottom-nav__item--active': isActive(link.to) }"
    >
      <v-icon size="24">
        {{ link.icon }}
      </v-icon>
      <span class="app-bottom-nav__label">{{ link.title }}</span>
    </NuxtLink>

    <button
      type="button"
      class="app-bottom-nav__item"
      @click="$emit('more')"
    >
      <v-icon size="24">
        {{ $globals.icons.menu }}
      </v-icon>
      <span class="app-bottom-nav__label">More</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import type { SidebarLinks } from "~/types/application-types";

defineProps({
  links: {
    type: Array as () => SidebarLinks,
    required: true,
  },
});

defineEmits<{ more: [] }>();

const { $globals } = useNuxtApp();
const route = useRoute();

function isActive(to?: string) {
  if (!to) {
    return false;
  }
  return route.path === to || route.path.startsWith(`${to}/`);
}
</script>

<style scoped>
.app-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2010;
  display: flex;
  align-items: stretch;
  height: 64px;
  padding-bottom: env(safe-area-inset-bottom);
  border-top: 1px solid rgba(var(--v-border-color), 0.12);
  box-shadow: 0 -2px 12px rgba(43, 37, 33, 0.06);
}

.app-bottom-nav__item {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.6);
  text-decoration: none;
  transition: color 0.15s ease;
}

.app-bottom-nav__item--active {
  color: rgb(var(--v-theme-primary));
}

.app-bottom-nav__label {
  font-family: var(--font-body);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}
</style>
