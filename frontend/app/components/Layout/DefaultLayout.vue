<template>
  <v-app dark>
    <TheSnackbar />

    <AppHeader />

    <AppSidebar
      v-model="sidebar"
      :permanent="lgAndUp"
      :top-link="topLinks"
      :secondary-links="cookbookLinks || []"
    >
      <v-btn
        v-if="isOwnGroup"
        rounded
        size="large"
        class="ml-2 mt-3"
        variant="elevated"
        elevation="2"
        :color="$vuetify.theme.current.dark ? 'background-lighten-1' : 'background-darken-1'"
        @click="quickAdd = true"
      >
        <v-icon
          start
          size="large"
          color="primary"
        >
          {{ $globals.icons.createAlt }}
        </v-icon>
        {{ $t("general.create") }}
      </v-btn>
    </AppSidebar>

    <RecipeQuickAddDialog v-model="quickAdd" />

    <v-btn
      v-if="!lgAndUp && isOwnGroup"
      class="quick-add-fab"
      icon
      color="primary"
      elevation="6"
      size="large"
      @click="quickAdd = true"
    >
      <v-icon size="28">
        {{ $globals.icons.createAlt }}
      </v-icon>
    </v-btn>

    <AppBottomNav
      v-if="!lgAndUp"
      :links="bottomNavLinks"
      @more="sidebar = true"
    />

    <v-main
      class="pt-12"
      :class="{ 'pb-16': !lgAndUp }"
    >
      <v-scroll-x-transition>
        <div>
          <NuxtPage />
        </div>
      </v-scroll-x-transition>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { useLoggedInState } from "~/composables/use-logged-in-state";
import type { SideBarLink } from "~/types/application-types";
import { useCookbookPreferences } from "~/composables/use-users/preferences";
import { useCookbookStore, usePublicCookbookStore } from "~/composables/store/use-cookbook-store";
import type { ReadCookBook } from "~/lib/api/types/cookbook";

const i18n = useI18n();
const { $globals } = useNuxtApp();
const display = useDisplay();
const lgAndUp = display.lgAndUp;
const auth = useMealieAuth();
const { isOwnGroup } = useLoggedInState();

const route = useRoute();
const groupSlug = computed(() => route.params.groupSlug as string || auth.user.value?.groupSlug || "");

const quickAdd = ref(false);

const cookbookPreferences = useCookbookPreferences();
const ownCookbookStore = computed(() => isOwnGroup.value ? useCookbookStore(i18n) : null);
const publicCookbookStoreCache = ref<Record<string, ReturnType<typeof usePublicCookbookStore>>>({});

function getPublicCookbookStore(slug: string) {
  if (!publicCookbookStoreCache.value[slug]) {
    publicCookbookStoreCache.value[slug] = usePublicCookbookStore(slug, i18n);
  }
  return publicCookbookStoreCache.value[slug];
}

const cookbooks = computed(() => {
  if (ownCookbookStore.value) {
    return ownCookbookStore.value.store.value;
  }
  else if (groupSlug.value) {
    const publicStore = getPublicCookbookStore(groupSlug.value);
    return unref(publicStore.store);
  }
  return [];
});

const sidebar = ref<boolean>(false);
onMounted(() => {
  sidebar.value = display.lgAndUp.value;
});

function cookbookAsLink(cookbook: ReadCookBook): SideBarLink {
  return {
    key: cookbook.slug || "",
    icon: $globals.icons.pages,
    title: cookbook.name,
    to: `/g/${groupSlug.value}/cookbooks/${cookbook.slug || ""}`,
    restricted: false,
  };
}

const currentUserHouseholdId = computed(() => auth.user.value?.householdId);
const cookbookLinks = computed<SideBarLink[]>(() => {
  if (!cookbooks.value?.length) {
    return [];
  }

  const sortedCookbooks = [...cookbooks.value].sort((a, b) => (a.position || 0) - (b.position || 0));

  const ownLinks: SideBarLink[] = [];
  const links: SideBarLink[] = [];
  const cookbooksByHousehold = sortedCookbooks.reduce((acc, cookbook) => {
    const householdName = cookbook.household?.name || "";
    (acc[householdName] ||= []).push(cookbook);
    return acc;
  }, {} as Record<string, ReadCookBook[]>);

  Object.entries(cookbooksByHousehold).forEach(([householdName, cookbooks]) => {
    if (!cookbooks.length) {
      return;
    }
    if (cookbooks[0].householdId === currentUserHouseholdId.value) {
      ownLinks.push(...cookbooks.map(cookbookAsLink));
    }
    else {
      links.push({
        key: householdName,
        icon: $globals.icons.book,
        title: householdName,
        children: cookbooks.map(cookbookAsLink),
        restricted: false,
      });
    }
  });

  links.sort((a, b) => a.title.localeCompare(b.title));
  if (auth.user.value && cookbookPreferences.value.hideOtherHouseholds) {
    return ownLinks;
  }
  else {
    return [...ownLinks, ...links];
  }
});

// Primary destinations for the mobile bottom nav (excludes nested/grouped links).
const bottomNavLinks = computed<SideBarLink[]>(() =>
  topLinks.value
    .filter(link => link.to && (!link.restricted || isOwnGroup.value))
    .slice(0, 4),
);

const topLinks = computed<SideBarLink[]>(() => [
  {
    icon: $globals.icons.silverwareForkKnife,
    to: `/g/${groupSlug.value}`,
    title: i18n.t("general.recipes"),
    restricted: false,
  },
  {
    icon: $globals.icons.search,
    to: `/g/${groupSlug.value}/recipes/finder`,
    title: i18n.t("recipe-finder.recipe-finder"),
    restricted: false,
  },
  {
    icon: $globals.icons.calendarMultiselect,
    title: i18n.t("meal-plan.meal-planner"),
    to: "/household/mealplan/planner/view",
    restricted: true,
  },
  {
    icon: $globals.icons.formatListCheck,
    title: i18n.t("shopping-list.shopping-lists"),
    to: "/shopping-lists",
    restricted: true,
  },
  {
    icon: $globals.icons.timelineText,
    title: i18n.t("recipe.timeline"),
    to: `/g/${groupSlug.value}/recipes/timeline`,
    restricted: true,
  },
  {
    icon: $globals.icons.book,
    to: `/g/${groupSlug.value}/cookbooks`,
    title: i18n.t("cookbook.cookbooks"),
    restricted: true,
  },
  {
    icon: $globals.icons.organizers,
    title: i18n.t("general.organizers"),
    restricted: true,
    children: [
      {
        icon: $globals.icons.categories,
        to: `/g/${groupSlug.value}/recipes/categories`,
        title: i18n.t("sidebar.categories"),
        restricted: true,
      },
      {
        icon: $globals.icons.tags,
        to: `/g/${groupSlug.value}/recipes/tags`,
        title: i18n.t("sidebar.tags"),
        restricted: true,
      },
      {
        icon: $globals.icons.potSteam,
        to: `/g/${groupSlug.value}/recipes/tools`,
        title: i18n.t("tool.tools"),
        restricted: true,
      },
    ],
  },
]);
</script>

<style scoped>
.quick-add-fab {
  position: fixed;
  right: 16px;
  bottom: calc(80px + env(safe-area-inset-bottom));
  z-index: 2011;
}
</style>
