<script setup lang="ts">
import { computed, watch } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useProfileStore } from "@/stores/profile";

const auth = useAuthStore();
const profileStore = useProfileStore();
const route = useRoute();

// Admin section has its own layout (sidebar). Hide the public topbar there.
// Kiosk page is full-screen; no topbar either.
const hideTopbar = computed(
  () => route.path.startsWith("/admin") || route.path.startsWith("/kiosk"),
);

// Drop cached profile when the user signs out / changes.
watch(
  () => auth.session?.user?.id ?? null,
  (uid, prev) => {
    if (uid !== prev) profileStore.clear();
  },
);

async function signOut() {
  profileStore.clear();
  await auth.signOut();
}
</script>

<template>
  <!-- Admin / kiosk routes render full-screen — no public topbar. -->
  <RouterView v-if="hideTopbar" />

  <div v-else class="layout" :class="{ 'has-tabbar': !!auth.session }">
    <header class="topbar">
      <RouterLink to="/" class="brand">
        <span class="dot" />
        <span class="brand-full">Marist Time Machine</span>
        <span class="brand-short">Time Machine</span>
      </RouterLink>
      <nav v-if="auth.session" class="topbar-nav">
        <!-- Desktop-only links (mobile uses the bottom tabbar) -->
        <RouterLink to="/capture" class="desktop-only">Buscar</RouterLink>
        <RouterLink to="/upload" class="desktop-only">Adicionar</RouterLink>
        <RouterLink to="/contribute" class="desktop-only">Identificar</RouterLink>
        <RouterLink to="/musicas" class="desktop-only">Músicas</RouterLink>
        <RouterLink to="/perfil" class="icon-link desktop-only" title="Meu perfil">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </RouterLink>
        <RouterLink to="/admin" class="icon-link" title="Painel administrativo">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </RouterLink>
        <button class="link" @click="signOut">Sair</button>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>

    <!-- Bottom tab bar (mobile only) -->
    <nav v-if="auth.session" class="tabbar" aria-label="Navegação principal">
      <RouterLink to="/capture" class="tab" active-class="active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="7"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <span>Buscar</span>
      </RouterLink>
      <RouterLink to="/upload" class="tab" active-class="active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 13V3"/><path d="m7 8 5-5 5 5"/><path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6"/>
        </svg>
        <span>Adicionar</span>
      </RouterLink>
      <RouterLink to="/contribute" class="tab" active-class="active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M4 21v-2a4 4 0 0 1 3-3.87"/>
          <circle cx="12" cy="7" r="4"/>
          <path d="m9 17 2 2 4-4"/>
        </svg>
        <span>Identificar</span>
      </RouterLink>
      <RouterLink to="/musicas" class="tab" active-class="active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 18V5l12-2v13"/>
          <circle cx="6" cy="18" r="3"/>
          <circle cx="18" cy="16" r="3"/>
        </svg>
        <span>Músicas</span>
      </RouterLink>
      <RouterLink to="/perfil" class="tab" active-class="active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
        <span>Perfil</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.icon-link {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem;
}

/* ----- Mobile topbar: collapse the link nav ----- */
.topbar-nav .desktop-only { display: none; }
@media (min-width: 720px) {
  .topbar-nav .desktop-only { display: inline-flex; }
}

/* ----- Bottom tab bar (mobile only) ----- */
.tabbar {
  position: fixed;
  inset: auto 0 0 0;
  z-index: 15;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  background: var(--marista-navy);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: min(var(--safe-bottom), 40px);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.15);
}
.tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
  padding: 0.55rem 0.25rem 0.4rem;
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  min-height: 56px;
  transition: color 0.12s;
}
.tab svg {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}
.tab:hover { color: var(--marista-white); }
.tab.active {
  color: var(--marista-yellow);
}

/* Hide on desktop — that uses the topbar nav links instead. */
@media (min-width: 720px) {
  .tabbar { display: none; }
}
</style>
