<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import FaceThumb from "@/components/FaceThumb.vue";
import { peopleApi, type Face, type Person } from "@/services/api";

const people = ref<Person[]>([]);
const loading = ref(true);
const thumbCache = ref<Record<string, Face | null>>({});
const query = ref("");

async function load() {
  loading.value = true;
  try {
    people.value = await peopleApi.list();
    await Promise.all(
      people.value.map(async (p) => {
        if (thumbCache.value[p.id]) return;
        try {
          const fs = await peopleApi.faces(p.id);
          thumbCache.value[p.id] = fs[0] ?? null;
        } catch {
          thumbCache.value[p.id] = null;
        }
      }),
    );
  } finally {
    loading.value = false;
  }
}

const filtered = () =>
  people.value.filter((p) => {
    if (!query.value.trim()) return true;
    const q = query.value.toLowerCase();
    return (p.display_name ?? "").toLowerCase().includes(q);
  });

onMounted(load);
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Pessoas</h1>
      <p class="muted">Todos os clusters de rostos detectados. Clique pra editar.</p>
    </div>
    <input v-model="query" class="input search" placeholder="Buscar pelo nome…" />
  </header>

  <p v-if="loading" class="muted">Carregando…</p>
  <p v-else-if="!people.length" class="muted">
    Nenhuma pessoa ainda. Suba mais fotos ou rode "Reagrupar agora" no painel.
  </p>
  <div v-else class="people-grid">
    <RouterLink
      v-for="p in filtered()"
      :key="p.id"
      :to="{ name: 'person', params: { id: p.id } }"
      class="person-card"
    >
      <FaceThumb
        v-if="thumbCache[p.id]"
        :src="thumbCache[p.id]!.signed_url"
        :bbox="thumbCache[p.id]!.bbox"
        :size="96"
        :padding="0.3"
      />
      <div v-else class="thumb-placeholder">?</div>
      <strong class="name">{{ p.display_name || "Sem nome" }}</strong>
      <span class="muted small">{{ p.face_count }} {{ p.face_count === 1 ? "foto" : "fotos" }}</span>
    </RouterLink>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.25rem;
}
.page-header h1 { margin: 0; }
.page-header p { margin: 0.2rem 0 0; }
.input.search { max-width: 280px; }

.people-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}
.person-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 0.6rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  text-decoration: none;
  color: var(--text);
  text-align: center;
  transition: border-color 0.15s;
}
.person-card:hover { border-color: var(--marista-blue); }
.thumb-placeholder {
  width: 96px; height: 96px;
  border-radius: 8px;
  background: var(--surface-strong);
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 1.8rem;
}
.name {
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  color: var(--marista-navy);
}
.small { font-size: 0.78rem; }
</style>
