<template>
  <div class="info-editor">
    <v-text-field
      v-model="recipe.name"
      class="info-editor__name"
      placeholder="Recipe name"
      :rules="[validators.required]"
      variant="plain"
      hide-details="auto"
    />
    <v-textarea
      v-model="recipe.description"
      auto-grow
      rows="2"
      class="mt-2"
      :label="$t('recipe.description')"
      density="comfortable"
      variant="outlined"
      rounded="lg"
    />

    <v-row
      dense
      class="mt-1"
    >
      <v-col
        cols="6"
        md="2"
      >
        <v-number-input
          :model-value="recipe.recipeServings"
          :min="0"
          :precision="null"
          density="compact"
          :label="$t('recipe.servings')"
          variant="outlined"
          rounded="lg"
          control-variant="hidden"
          hide-details
          @update:model-value="recipe.recipeServings = $event"
        />
      </v-col>
      <v-col
        cols="6"
        md="2"
      >
        <v-number-input
          :model-value="recipe.recipeYieldQuantity"
          :min="0"
          :precision="null"
          density="compact"
          :label="$t('recipe.yield')"
          variant="outlined"
          rounded="lg"
          control-variant="hidden"
          hide-details
          @update:model-value="recipe.recipeYieldQuantity = $event"
        />
      </v-col>
      <v-col
        cols="12"
        md="2"
      >
        <v-text-field
          v-model="recipe.recipeYield"
          density="compact"
          :label="$t('recipe.yield-text')"
          variant="outlined"
          rounded="lg"
          hide-details
        />
      </v-col>
      <v-col
        cols="4"
        md="2"
      >
        <v-text-field
          v-model="recipe.prepTime"
          :label="$t('recipe.prep-time')"
          density="compact"
          variant="outlined"
          rounded="lg"
          hide-details
        />
      </v-col>
      <v-col
        cols="4"
        md="2"
      >
        <v-text-field
          v-model="recipe.performTime"
          :label="$t('recipe.perform-time')"
          density="compact"
          variant="outlined"
          rounded="lg"
          hide-details
        />
      </v-col>
      <v-col
        cols="4"
        md="2"
      >
        <v-text-field
          v-model="recipe.totalTime"
          :label="$t('recipe.total-time')"
          density="compact"
          variant="outlined"
          rounded="lg"
          hide-details
        />
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { validators } from "~/composables/use-validators";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import type { Recipe } from "~/lib/api/types/recipe";

const recipe = defineModel<NoUndefinedField<Recipe>>({ required: true });
</script>

<style scoped>
.info-editor__name :deep(input) {
  font-family: var(--font-display);
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  font-weight: 600;
  line-height: 1.2;
}

.info-editor__name :deep(.v-field__input) {
  padding-top: 4px;
  padding-bottom: 4px;
}
</style>
