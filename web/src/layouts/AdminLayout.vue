<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useProfileStore } from "@/stores/profile";
import {
  peopleApi,
  suggestionsApi,
  facesApi,
  moderationApi,
  songsModerationApi,
} from "@/services/api";

const auth = useAuthStore();
const profileStore = useProfileStore();

async function handleSignOut() {
  profileStore.clear();
  await auth.signOut();
}
const route = useRoute();

const drawerOpen = ref(false);
const counts = ref({
  people: 0,
  unassigned: 0,
  suggestions: 0,
  pendingPhotos: 0,
  pendingSongs: 0,
});

async function refreshCounts() {
  try {
    const [stats, list, faces, modCounts, songCounts] = await Promise.all([
      peopleApi.stats().catch(() => null),
      suggestionsApi.pendingByTarget().catch(() => []),
      facesApi.unassigned(1, 0, 0.5).catch(() => []),
      moderationApi.counts().catch(() => ({ pending: 0, approved: 0, rejected: 0 })),
      songsModerationApi.counts().catch(() => ({ pending: 0, approved: 0, rejected: 0 })),
    ]);
    if (stats) counts.value.people = stats.people;
    counts.value.suggestions = list.length;
    if (stats) counts.value.unassigned = Math.max(0, stats.faces_total - stats.faces_clustered);
    counts.value.pendingPhotos = modCounts.pending;
    counts.value.pendingSongs = songCounts.pending;
    void faces;
  } catch {
    /* silent */
  }
}

onMounted(refreshCounts);
watch(() => route.fullPath, () => {
  drawerOpen.value = false;
});

const userEmail = computed(() => auth.session?.user?.email ?? "");
const userInitial = computed(() => userEmail.value.slice(0, 1).toUpperCase());
</script>

<template>
  <div class="admin-shell" :class="{ 'drawer-open': drawerOpen }">
    <!-- Mobile top bar (only visible on small screens) -->
    <header class="admin-topbar">
      <button class="hamburger" @click="drawerOpen = !drawerOpen" aria-label="Menu">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <RouterLink to="/admin" class="admin-brand">
        <span class="brand-dot" />
        <span class="brand-name">Marist Time Machine</span>
      </RouterLink>
      <RouterLink to="/" class="exit-icon" aria-label="Sair do admin">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
          <polyline points="16 17 21 12 16 7"/>
          <line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
      </RouterLink>
    </header>

    <!-- Sidebar -->
    <aside class="admin-sidebar" :class="{ open: drawerOpen }">
      <RouterLink to="/admin" class="sidebar-brand">
        <span class="brand-dot" />
        <span>Marist Time Machine</span>
      </RouterLink>

      <nav class="sidebar-nav">
        <RouterLink to="/admin" class="nav-item" exact-active-class="active">
          <span class="icon">📊</span>
          <span>Painel</span>
        </RouterLink>

        <div class="nav-section">Acervo</div>
        <RouterLink to="/admin/pessoas" class="nav-item">
          <span class="icon">👥</span>
          <span>Pessoas</span>
          <span v-if="counts.people" class="count">{{ counts.people }}</span>
        </RouterLink>
        <RouterLink to="/admin/nao-atribuidos" class="nav-item">
          <span class="icon">🔍</span>
          <span>Não atribuídos</span>
          <span v-if="counts.unassigned" class="count">{{ counts.unassigned }}</span>
        </RouterLink>

        <div class="nav-section">Moderação</div>
        <RouterLink to="/admin/fotos" class="nav-item">
          <span class="icon">📷</span>
          <span>Fotos</span>
          <span v-if="counts.pendingPhotos" class="count badge-yellow">{{ counts.pendingPhotos }}</span>
        </RouterLink>
        <RouterLink to="/admin/musicas" class="nav-item">
          <span class="icon">🎵</span>
          <span>Músicas</span>
          <span v-if="counts.pendingSongs" class="count badge-yellow">{{ counts.pendingSongs }}</span>
        </RouterLink>
        <RouterLink to="/admin/sugestoes" class="nav-item">
          <span class="icon">🏷️</span>
          <span>Sugestões</span>
          <span v-if="counts.suggestions" class="count badge-yellow">{{ counts.suggestions }}</span>
        </RouterLink>

        <div class="nav-section">Sistema</div>
        <RouterLink to="/admin/status" class="nav-item">
          <span class="icon">⚙️</span>
          <span>Status</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="user-card">
          <div class="avatar">{{ userInitial }}</div>
          <div class="user-info">
            <strong>{{ userEmail }}</strong>
            <span class="muted small">Administrador</span>
          </div>
        </div>
        <div class="actions">
          <RouterLink to="/" class="link-out">← Voltar ao app</RouterLink>
          <button class="link-out danger" @click="handleSignOut">Sair</button>
        </div>
      </div>
    </aside>

    <!-- Mobile backdrop -->
    <div
      v-if="drawerOpen"
      class="drawer-backdrop"
      @click="drawerOpen = false"
    ></div>

    <!-- Main content -->
    <main class="admin-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.admin-shell {
  display: grid;
  grid-template-columns: 1fr;
  /* Explicit rows: topbar takes its natural height, main fills the rest.
     Without this, on some viewports the topbar can stretch to fill the
     grid row when no explicit row is declared. */
  grid-template-rows: auto 1fr;
  min-height: 100vh;
  min-height: 100svh;
  background: var(--bg);
}

/* Mobile-first topbar */
.admin-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  /* Cap the safe-area-inset so a misreported value (some PWAs return huge
     numbers) can't blow up the topbar height. iPhone notch maxes ~50px. */
  padding-top: calc(0.7rem + min(var(--safe-top), 50px));
  padding-right: 1rem;
  padding-bottom: 0.7rem;
  padding-left: 1rem;
  min-height: 56px;
  max-height: calc(56px + min(var(--safe-top), 50px));
  flex: 0 0 auto;
  background: var(--marista-navy);
  color: var(--marista-white);
  border-bottom: 3px solid var(--marista-yellow);
  position: sticky;
  top: 0;
  z-index: 12;
}
.hamburger, .exit-icon {
  background: none;
  border: none;
  color: var(--marista-white);
  padding: 0.4rem;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.admin-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--marista-white);
  text-decoration: none;
  font-weight: 700;
  font-size: 0.95rem;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.brand-dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--marista-yellow);
  flex-shrink: 0;
}

/* Sidebar */
.admin-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 260px;
  background: var(--marista-navy);
  color: var(--marista-white);
  z-index: 14;
  transform: translateX(-100%);
  transition: transform 0.2s ease;
  display: flex;
  flex-direction: column;
  padding-top: min(var(--safe-top), 50px);
  padding-bottom: min(var(--safe-bottom), 50px);
}
.admin-sidebar.open { transform: translateX(0); }

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 1.1rem 1.2rem;
  font-weight: 700;
  font-size: 1rem;
  color: var(--marista-white);
  text-decoration: none;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
}
.nav-section {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.4);
  padding: 1rem 1.2rem 0.4rem;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.65rem 1.2rem;
  color: rgba(255,255,255,0.78);
  text-decoration: none;
  font-size: 0.95rem;
  position: relative;
  border-left: 3px solid transparent;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover {
  background: rgba(255,255,255,0.06);
  color: var(--marista-white);
}
.nav-item.router-link-exact-active,
.nav-item.router-link-active:not(.no-active) {
  background: rgba(255,255,255,0.1);
  color: var(--marista-yellow);
  border-left-color: var(--marista-yellow);
}
.nav-item .icon {
  font-size: 1.05rem;
  width: 22px;
  text-align: center;
  flex-shrink: 0;
}
.nav-item .count {
  margin-left: auto;
  background: rgba(255,255,255,0.12);
  color: var(--marista-white);
  font-size: 0.72rem;
  border-radius: 99px;
  padding: 0.1rem 0.5rem;
  font-weight: 600;
}
.nav-item .count.badge-yellow {
  background: var(--marista-yellow);
  color: var(--marista-navy);
}

.sidebar-footer {
  border-top: 1px solid rgba(255,255,255,0.08);
  padding: 0.85rem 1.2rem;
}
.user-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 0.65rem;
  min-width: 0;
}
.avatar {
  width: 34px; height: 34px;
  border-radius: 50%;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.user-info strong {
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--marista-white);
}
.user-info .small { color: rgba(255,255,255,0.55); }

.actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.link-out {
  display: inline-block;
  color: rgba(255,255,255,0.6);
  text-decoration: none;
  font-size: 0.85rem;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
}
.link-out:hover { color: var(--marista-white); }
.link-out.danger:hover { color: var(--marista-pink); }

.drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 13;
  backdrop-filter: blur(2px);
}

.admin-main {
  padding: 1rem;
  min-width: 0;
  padding-bottom: calc(1rem + var(--safe-bottom));
}

/* Desktop: sidebar always visible */
@media (min-width: 960px) {
  .admin-shell {
    grid-template-columns: 260px 1fr;
  }
  .admin-topbar { display: none; }
  .admin-sidebar {
    position: sticky;
    top: 0;
    height: 100vh;
    transform: none;
    border-right: 1px solid rgba(255,255,255,0.08);
  }
  .drawer-backdrop { display: none; }
  .admin-main {
    padding: 1.5rem 2rem;
    max-width: 1280px;
  }
}
</style>
