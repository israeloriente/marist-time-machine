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
        Marist Time Machine
      </RouterLink>
      <nav v-if="auth.session">
        <RouterLink to="/capture">Buscar</RouterLink>
        <button class="link" @click="auth.signOut">Sair</button>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>
