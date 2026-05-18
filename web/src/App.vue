<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();

// Admin section has its own layout (sidebar). Hide the public topbar there.
const isAdmin = computed(() => route.path.startsWith("/admin"));
</script>

<template>
  <!-- Admin routes render their own layout (sidebar) — no public topbar. -->
  <RouterView v-if="isAdmin" />

  <div v-else class="layout">
    <header class="topbar">
      <RouterLink to="/" class="brand">
        <span class="dot" />
        <span class="brand-full">Marist Time Machine</span>
        <span class="brand-short">Time Machine</span>
      </RouterLink>
      <nav v-if="auth.session">
        <RouterLink to="/capture">Buscar</RouterLink>
        <RouterLink to="/upload">Adicionar</RouterLink>
        <RouterLink to="/contribute">Identificar</RouterLink>
        <RouterLink to="/admin" class="admin-link" title="Painel administrativo">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </RouterLink>
        <button class="link" @click="auth.signOut">Sair</button>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.admin-link {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem;
}
</style>
