<script setup lang="ts">
import { RouterLink } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
</script>

<template>
  <section class="card">
    <h1>Volte no tempo.</h1>
    <p class="muted">
      Tire uma selfie e a gente encontra todas as suas fotos no acervo Marista.
    </p>
    <div style="margin-top: 1.5rem; display: flex; gap: 0.75rem;">
      <RouterLink v-if="auth.session" to="/capture" class="button">Buscar agora</RouterLink>
      <RouterLink v-else to="/login" class="button">Entrar para buscar</RouterLink>
    </div>
  </section>
</template>
