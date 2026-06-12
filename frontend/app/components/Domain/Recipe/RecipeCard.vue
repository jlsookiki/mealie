<template>
  <!-- Wrap v-hover with a div to provide a proper DOM element for the transition -->
  <div class="recipe-card__wrap">
    <v-hover
      v-slot="{ isHovering, props: hoverProps }"
      :open-delay="50"
    >
      <v-card
        v-bind="hoverProps"
        :class="['recipe-card', { 'on-hover': isHovering }]"
        :style="{ cursor }"
        :elevation="isHovering ? 12 : 2"
        :to="recipeRoute"
        @click.self="$emit('click')"
      >
        <div class="recipe-card__media">
          <RecipeCardImage
            small
            :icon-size="imageHeight"
            :height="imageHeight"
            :slug="slug"
            :recipe-id="recipeId"
            :image-version="image"
          />
        </div>

        <v-card-title class="recipe-card__title px-4 pt-3 pb-0">
          {{ name }}
        </v-card-title>

        <!-- Always rendered (even when empty) so every card is the same height -->
        <div class="recipe-card__desc px-4 pt-1">
          <SafeMarkdown
            v-if="description"
            :source="description"
          />
        </div>

        <slot name="actions">
          <v-card-actions
            v-if="showRecipeContent"
            class="recipe-card__actions px-2 pb-1"
          >
            <RecipeFavoriteBadge
              v-if="isOwnGroup"
              :recipe-id="recipeId"
              show-always
            />
            <div v-else class="px-1" /> <!-- Empty div to keep the layout consistent -->

            <RecipeCardRating
              v-if="rating"
              :model-value="rating"
              :recipe-id="recipeId"
            />
            <v-spacer />
            <div class="recipe-card__chips">
              <RecipeChips
                :truncate="true"
                :items="tags"
                :title="false"
                :limit="2"
                small
                url-prefix="tags"
                v-bind="$attrs"
              />
            </div>

            <!-- If we're not logged-in, no items display, so we hide this menu -->
            <RecipeContextMenu
              v-if="isOwnGroup && showRecipeContent"
              color="grey-darken-2"
              :slug="slug"
              :menu-icon="$globals.icons.dotsVertical"
              :name="name"
              :recipe-id="recipeId"
              :use-items="{
                delete: false,
                edit: false,
                download: true,
                mealplanner: true,
                shoppingList: true,
                print: false,
                printPreferences: false,
                share: true,
              }"
              @deleted="$emit('delete', slug)"
            />
          </v-card-actions>
        </slot>
        <slot />
      </v-card>
    </v-hover>
  </div>
</template>

<script setup lang="ts">
import RecipeFavoriteBadge from "./RecipeFavoriteBadge.vue";
import RecipeChips from "./RecipeChips.vue";
import RecipeContextMenu from "./RecipeContextMenu/RecipeContextMenu.vue";
import RecipeCardImage from "./RecipeCardImage.vue";
import RecipeCardRating from "./RecipeCardRating.vue";
import { useLoggedInState } from "~/composables/use-logged-in-state";

interface Props {
  name: string;
  slug: string;
  description?: string | null;
  rating?: number;
  ratingColor?: string;
  image?: string;
  tags?: Array<any>;
  recipeId: string;
  imageHeight?: number;
}
const props = withDefaults(defineProps<Props>(), {
  description: null,
  rating: 0,
  ratingColor: "secondary",
  image: "abc123",
  tags: () => [],
  imageHeight: 200,
});

defineEmits<{
  click: [];
  delete: [slug: string];
}>();

const auth = useMealieAuth();
const { isOwnGroup } = useLoggedInState();

const route = useRoute();
const groupSlug = computed(() => route.params.groupSlug || auth.user.value?.groupSlug || "");
const showRecipeContent = computed(() => props.recipeId && props.slug);
const recipeRoute = computed<string>(() => {
  return showRecipeContent.value ? `/g/${groupSlug.value}/r/${props.slug}` : "";
});
const cursor = computed(() => showRecipeContent.value ? "pointer" : "auto");
</script>

<style scoped>
.recipe-card__wrap {
  height: 100%;
}
.recipe-card {
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.recipe-card.on-hover {
  transform: translateY(-3px);
}
.recipe-card__media {
  overflow: hidden;
}
.recipe-card__media :deep(.v-img) {
  transition: transform 0.4s ease;
}
.recipe-card.on-hover .recipe-card__media :deep(.v-img) {
  transform: scale(1.05);
}
.recipe-card__title {
  font-size: 1.2rem;
  line-height: 1.25;
  font-weight: 600;
  white-space: normal;
  word-break: normal;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  /* Exactly two lines tall whether the name uses one or two (12px = pt-3) */
  height: calc(2 * 1.25em + 12px);
}
.recipe-card__desc {
  font-size: 0.85rem;
  line-height: 1.4;
  color: rgba(var(--v-theme-on-surface), 0.6);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  /* Fixed two-line block even when there is no description */
  height: calc(2 * 1.4em + 4px);
}
.recipe-card__actions {
  /* Pin to the card bottom at a fixed height; never let chips wrap */
  margin-top: auto;
  flex-wrap: nowrap;
  overflow: hidden;
  min-width: 0;
  height: 60px;
}
.recipe-card__chips {
  min-width: 0;
  overflow: hidden;
}
.recipe-card__chips > :deep(div) {
  display: flex;
  flex-wrap: nowrap;
  white-space: nowrap;
}
.recipe-card__chips :deep(.v-chip) {
  flex-shrink: 0;
}
</style>
