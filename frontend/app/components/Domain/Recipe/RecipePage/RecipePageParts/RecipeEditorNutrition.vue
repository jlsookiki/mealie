<template>
  <section>
    <div class="editor-section__header mb-3">
      <h2 class="editor-section__title">
        {{ $t("recipe.nutrition") }}
      </h2>
      <div class="editor-section__rule" />
    </div>

    <RecipeNutritionCalculator
      v-model="recipe.nutrition"
      :recipe="recipe"
      @enable-nutrition="recipe.settings.showNutrition = true"
    />

    <v-expand-transition>
      <div v-if="fieldsOpen">
        <RecipeNutrition
          v-model="recipe.nutrition"
          :edit="true"
        />
      </div>
    </v-expand-transition>

    <div class="d-flex align-center mt-2">
      <v-btn
        variant="text"
        size="small"
        @click="fieldsOpen = !fieldsOpen"
      >
        <v-icon
          start
          :icon="fieldsOpen ? mdiChevronUp : mdiChevronDown"
        />
        {{ fieldsOpen ? "Hide values" : "Edit values manually" }}
      </v-btn>
      <v-spacer />
      <v-switch
        v-model="recipe.settings.showNutrition"
        color="primary"
        density="compact"
        hide-details
        inset
        :label="$t('recipe.show-nutrition-values')"
        class="flex-grow-0"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { mdiChevronDown, mdiChevronUp } from "@mdi/js";
import type { Recipe } from "~/lib/api/types/recipe";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import RecipeNutrition from "~/components/Domain/Recipe/RecipeNutrition.vue";
import RecipeNutritionCalculator from "~/components/Domain/Recipe/RecipeNutritionCalculator.vue";

const recipe = defineModel<NoUndefinedField<Recipe>>({ required: true });

const fieldsOpen = ref(false);
</script>

<style scoped>
.editor-section__header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.editor-section__title {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.2;
}

.editor-section__rule {
  width: 44px;
  height: 3px;
  border-radius: 2px;
  background: rgb(var(--v-theme-primary));
}
</style>
