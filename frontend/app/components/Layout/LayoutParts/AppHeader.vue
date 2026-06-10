<template>
  <v-app-bar
    clipped-left
    flat
    app
    color="background"
    border="b"
    height="68"
    class="d-print-none app-header"
  >
    <slot />
    <RouterLink :to="routerLink">
      <v-btn
        icon
        color="primary"
      >
        <v-icon size="36"> {{ $globals.icons.primary }} </v-icon>
      </v-btn>
    </RouterLink>

    <div
      btn
      class="pl-1"
    >
      <v-toolbar-title
        class="app-wordmark"
        style="cursor: pointer"
        @click="$router.push(routerLink)"
      >
        Mealie
      </v-toolbar-title>
    </div>
    <RecipeDialogSearch ref="domSearchDialog" />

    <v-spacer />

    <!-- Navigation Menu -->
    <template v-if="menu">
      <v-responsive
        v-if="!xs"
        max-width="260"
        class="mr-2"
        @click="activateSearch"
      >
        <v-text-field
          readonly
          hide-details
          rounded="xl"
          variant="outlined"
          density="compact"
          :prepend-inner-icon="$globals.icons.search"
          :placeholder="$t('search.search-hint')"
        />
      </v-responsive>
      <v-btn
        v-else
        icon
        @click="activateSearch"
      >
        <v-icon> {{ $globals.icons.search }}</v-icon>
      </v-btn>
      <v-btn
        v-if="loggedIn"
        :variant="smAndUp ? 'text' : undefined"
        :icon="xs"
        @click="logout()"
      >
        <v-icon :start="smAndUp">
          {{ $globals.icons.logout }}
        </v-icon>
        {{ smAndUp ? $t("user.logout") : "" }}
      </v-btn>
      <v-btn
        v-else
        variant="text"
        nuxt
        to="/login"
      >
        <v-icon start>
          {{ $globals.icons.user }}
        </v-icon>
        {{ $t("user.login") }}
      </v-btn>
    </template>
  </v-app-bar>
</template>

<script setup lang="ts">
import { useLoggedInState } from "~/composables/use-logged-in-state";
import type RecipeDialogSearch from "~/components/Domain/Recipe/RecipeDialogSearch.vue";

defineProps({
  menu: {
    type: Boolean,
    default: true,
  },
});
const auth = useMealieAuth();
const { loggedIn } = useLoggedInState();
const route = useRoute();
const groupSlug = computed(() => route.params.groupSlug as string || auth.user.value?.groupSlug || "");
const { xs, smAndUp } = useDisplay();

const routerLink = computed(() => groupSlug.value ? `/g/${groupSlug.value}` : "/");
const domSearchDialog = ref<InstanceType<typeof RecipeDialogSearch> | null>(null);

function activateSearch() {
  domSearchDialog.value?.open();
}

function handleKeyEvent(e: KeyboardEvent) {
  const activeTag = document.activeElement?.tagName;
  if (e.key === "/" && activeTag !== "INPUT" && activeTag !== "TEXTAREA") {
    e.preventDefault();
    activateSearch();
  }
}

onMounted(() => {
  document.addEventListener("keydown", handleKeyEvent);
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleKeyEvent);
});

async function logout() {
  try {
    await auth.signOut("/login?direct=1");
  }
  catch (e) {
    console.error(e);
  }
}
</script>

<style scoped>
.v-toolbar {
  z-index: 2010 !important;
}

.app-wordmark {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 1.6rem;
  letter-spacing: -0.02em;
  color: rgb(var(--v-theme-primary));
}

/* Quiet outlined search: soften the border on the paper header */
.app-header :deep(.v-field__outline) {
  --v-field-border-opacity: 0.16;
}
</style>
