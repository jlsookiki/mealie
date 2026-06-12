<template>
  <v-container
    class="connect-page d-flex align-center justify-center"
    style="min-height: 80vh"
  >
    <v-card
      class="connect-card pa-2"
      max-width="430"
      width="100%"
    >
      <v-card-text class="px-6 py-7">
        <template v-if="invalidRequest">
          <h1 class="connect-card__title mb-2">
            Invalid request
          </h1>
          <p class="connect-card__sub mb-0">
            This authorization link is missing required parameters. Start the connection again from the app you're
            linking.
          </p>
        </template>

        <template v-else>
          <div class="connect-card__badge mb-4">
            <v-icon
              :icon="mdiLinkVariant"
              size="22"
            />
          </div>
          <h1 class="connect-card__title mb-2">
            Connect to Mealie
          </h1>
          <p class="connect-card__sub mb-6">
            <b>{{ clientName }}</b> wants access to your Mealie account — recipes, meal plans, and shopping lists. It
            will act as <b>{{ userName }}</b>.
          </p>

          <v-alert
            v-if="errorMessage"
            type="error"
            variant="tonal"
            density="comfortable"
            class="mb-4"
          >
            {{ errorMessage }}
          </v-alert>

          <v-btn
            color="primary"
            variant="flat"
            rounded="lg"
            size="large"
            block
            :loading="approving"
            @click="approve"
          >
            Approve
          </v-btn>
          <v-btn
            variant="text"
            rounded="lg"
            block
            class="mt-2"
            :disabled="approving"
            @click="deny"
          >
            Deny
          </v-btn>
          <p class="connect-card__hint mt-5 mb-0">
            Approving creates an API token in your profile (Manage API Tokens) — you can revoke this connection there
            at any time.
          </p>
        </template>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { mdiLinkVariant } from "@mdi/js";
import { useMealieAuth } from "~/composables/use-mealie-auth";

const route = useRoute();
const auth = useMealieAuth();

const clientName = ref("An application");
const errorMessage = ref("");
const approving = ref(false);

const q = computed(() => ({
  responseType: String(route.query.response_type || ""),
  clientId: String(route.query.client_id || ""),
  redirectUri: String(route.query.redirect_uri || ""),
  state: String(route.query.state || ""),
  codeChallenge: String(route.query.code_challenge || ""),
  codeChallengeMethod: String(route.query.code_challenge_method || ""),
}));

const invalidRequest = computed(
  () => q.value.responseType !== "code" || !q.value.clientId || !q.value.redirectUri,
);

const userName = computed(() => auth.user.value?.fullName || auth.user.value?.username || "you");

// Not logged in -> Mealie's own login, then bounce back here with the query intact.
watch(
  () => auth.loggedIn.value,
  (loggedIn) => {
    if (!loggedIn) {
      navigateTo({ path: "/login", query: { redirect: route.fullPath } });
    }
  },
  { immediate: true },
);

onMounted(async () => {
  if (invalidRequest.value) {
    return;
  }
  try {
    const info = await $fetch<{ client_name: string | null }>(
      `/api/fork/oauth/client/${encodeURIComponent(q.value.clientId)}`,
    );
    if (info.client_name) {
      clientName.value = info.client_name;
    }
  }
  catch {
    errorMessage.value = "This application isn't registered. Start the connection again.";
  }
});

async function approve() {
  approving.value = true;
  errorMessage.value = "";
  try {
    const res = await $fetch<{ redirect_url: string }>("/api/fork/oauth/authorize", {
      method: "POST",
      headers: { Authorization: `Bearer ${auth.token.value}` },
      body: {
        client_id: q.value.clientId,
        redirect_uri: q.value.redirectUri,
        state: q.value.state || null,
        code_challenge: q.value.codeChallenge || null,
        code_challenge_method: q.value.codeChallengeMethod || null,
      },
    });
    window.location.href = res.redirect_url;
  }
  catch {
    errorMessage.value = "Couldn't authorize the connection. Please try again.";
    approving.value = false;
  }
}

function deny() {
  const sep = q.value.redirectUri.includes("?") ? "&" : "?";
  let url = `${q.value.redirectUri}${sep}error=access_denied`;
  if (q.value.state) {
    url += `&state=${encodeURIComponent(q.value.state)}`;
  }
  window.location.href = url;
}
</script>

<style scoped>
.connect-card__badge {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.connect-card__title {
  font-family: var(--font-display);
  font-size: 1.6rem;
  font-weight: 600;
  line-height: 1.2;
}

.connect-card__sub {
  font-size: 0.92rem;
  opacity: 0.78;
  line-height: 1.5;
}

.connect-card__hint {
  font-size: 0.75rem;
  opacity: 0.55;
  line-height: 1.45;
}
</style>
