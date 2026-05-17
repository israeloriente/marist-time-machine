<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const email = ref("");
const password = ref("");
const mode = ref<"signin" | "signup">("signin");

async function submit() {
  if (mode.value === "signin") {
    await auth.signInWithEmail(email.value, password.value);
  } else {
    await auth.signUpWithEmail(email.value, password.value);
  }
  if (auth.session) {
    const redirect = (route.query.redirect as string) || "/capture";
    router.push(redirect);
  }
}
</script>

<template>
  <section class="card" style="max-width: 420px; margin: 2rem auto;">
    <h2>{{ mode === "signin" ? "Entrar" : "Criar conta" }}</h2>
    <form @submit.prevent="submit" style="display: flex; flex-direction: column; gap: 0.75rem;">
      <input v-model="email" type="email" class="input" placeholder="email" required autocomplete="email" />
      <input v-model="password" type="password" class="input" placeholder="senha" required autocomplete="current-password" minlength="6" />
      <button class="button" type="submit" :disabled="auth.loading">
        {{ auth.loading ? "..." : mode === "signin" ? "Entrar" : "Criar" }}
      </button>
      <p v-if="auth.error" class="error">{{ auth.error }}</p>
      <button
        type="button"
        class="link muted"
        style="background: none; border: none; cursor: pointer; align-self: center;"
        @click="mode = mode === 'signin' ? 'signup' : 'signin'"
      >
        {{ mode === "signin" ? "Não tem conta? Criar uma" : "Já tem conta? Entrar" }}
      </button>
    </form>
  </section>
</template>
