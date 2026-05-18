<script setup lang="ts">
import { RouterView, RouterLink } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
</script>

<template>
  <div class="layout">
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
        <RouterLink to="/admin">Admin</RouterLink>
        <button class="link" @click="auth.signOut">Sair</button>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>
