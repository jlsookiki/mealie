<template>
  <v-dialog
    v-model="open"
    max-width="480"
    :fullscreen="$vuetify.display.xs"
  >
    <v-card
      rounded="xl"
      class="pa-2"
    >
      <div class="d-flex align-center px-5 pt-5 pb-1">
        <h2 class="text-h5">
          {{ $t("recipe.recipe-settings") }}
        </h2>
        <v-spacer />
        <v-btn
          icon
          variant="text"
          @click="open = false"
        >
          <v-icon :icon="mdiClose" />
        </v-btn>
      </div>

      <v-card-text class="px-5 pt-2">
        <RecipeSettingsSwitches
          v-model="recipe.settings"
          :is-owner="recipe.userId === user.id"
        />

        <v-divider class="my-4" />

        <div class="settings-dialog__owner-label mb-2">
          {{ $t("general.owner") }}
        </div>
        <v-select
          v-model="recipe.userId"
          :items="allUsers"
          :item-props="itemsProps"
          :disabled="!canEditOwner"
          variant="outlined"
          density="compact"
          rounded="lg"
          hide-details
        >
          <template #prepend>
            <Transition
              name="save-swap"
              mode="out-in"
            >
              <UserAvatar
                :key="recipe.userId"
                :user-id="recipe.userId"
                :tooltip="false"
              />
            </Transition>
          </template>
        </v-select>
        <p class="settings-dialog__hint mt-3 mb-0">
          Changes apply when you save the recipe.
        </p>
      </v-card-text>

      <v-card-actions class="px-5 pb-4 pt-0">
        <v-spacer />
        <v-btn
          variant="text"
          color="primary"
          @click="open = false"
        >
          Done
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { mdiClose } from "@mdi/js";
import { usePageUser } from "~/composables/recipe-page/shared-state";
import type { NoUndefinedField } from "~/lib/api/types/non-generated";
import type { Recipe } from "~/lib/api/types/recipe";
import RecipeSettingsSwitches from "~/components/Domain/Recipe/RecipeSettingsSwitches.vue";
import UserAvatar from "~/components/Domain/User/UserAvatar.vue";
import { useUserStore } from "~/composables/store/use-user-store";
import { useHouseholdStore } from "~/composables/store";

const open = defineModel<boolean>({ default: false });
const recipe = defineModel<NoUndefinedField<Recipe>>("recipe", { required: true });

const { user } = usePageUser();

const canEditOwner = computed(() => {
  return user.id === recipe.value.userId || user.admin;
});

const { store: allUsers } = useUserStore();
const { store: households } = useHouseholdStore();

function itemsProps(item: any) {
  const owner = allUsers.value.find(u => u.id === item.id);
  return {
    value: item.id,
    title: item.fullName,
    subtitle: owner ? households.value.find(h => h.id === owner.householdId)?.name || "" : "",
  };
}
</script>

<style scoped>
.settings-dialog__owner-label {
  font-weight: 600;
  font-size: 0.9rem;
}

.settings-dialog__hint {
  font-size: 0.8rem;
  opacity: 0.55;
}

.save-swap-enter-active,
.save-swap-leave-active {
  transition: opacity var(--ms-dur-fast) var(--ms-ease);
}

.save-swap-enter-from,
.save-swap-leave-to {
  opacity: 0;
}
</style>
