<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import FaceThumb from "@/components/FaceThumb.vue";
import { peopleApi, type AvailableFilters, type Face, type Person } from "@/services/api";

const people = ref<Person[]>([]);
const loading = ref(true);
const thumbCache = ref<Record<string, Face | null>>({});

const query = ref("");
const year = ref<number | "">("");
const klass = ref<string>("");
const available = ref<AvailableFilters>({ years: [], classes: [] });

async function loadFilters() {
  try {
    available.value = await peopleApi.filters();
  } catch {
    /* silent */
  }
}

async function load() {
  loading.value = true;
  try {
    const filters: { year?: number; class?: string } = {};
    if (year.value !== "") filters.year = year.value;
    if (klass.value) filters.class = klass.value;
    people.value = await peopleApi.list(filters);
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

const filtered = computed(() => {
  if (!query.value.trim()) return people.value;
  const q = query.value.toLowerCase();
  return people.value.filter((p) => (p.display_name ?? "").toLowerCase().includes(q));
});

function clearFilters() {
  year.value = "";
  klass.value = "";
  query.value = "";
}

const hasFilters = computed(() => year.value !== "" || klass.value !== "" || query.value !== "");

watch([year, klass], load);

onMounted(async () => {
  await Promise.all([loadFilters(), load()]);
});
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Pessoas</h1>
      <p class="muted">
        Todos os clusters de rostos detectados. Filtre por ano/turma das fotos onde aparecem.
      </p>
    </div>
  </header>

  <section class="filters card">
    <div class="filter-grid">
      <label>
        <span>Buscar por nome</span>
        <input v-model="query" class="input" placeholder="Digite um nome…" />
      </label>
      <label>
        <span>Ano de formatura</span>
        <select v-model.number="year" class="input">
          <option value="">Todos os anos</option>
          <option v-for="y in available.years" :key="y" :value="y">{{ y }}</option>
        </select>
      </label>
      <label>
        <span>Turma</span>
        <select v-model="klass" class="input">
          <option value="">Todas as turmas</option>
          <option v-for="c in available.classes" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <button
        v-if="hasFilters"
        class="button secondary clear-btn"
        type="button"
        @click="clearFilters"
      >
        Limpar
      </button>
    </div>
  </section>

  <p v-if="loading" class="muted">Carregando…</p>
  <p v-else-if="!filtered.length" class="muted">
    <template v-if="hasFilters">
      Nenhuma pessoa nessa combinação de filtros.
    </template>
    <template v-else>
      Nenhuma pessoa ainda. Suba mais fotos ou rode "Reagrupar agora" no painel.
    </template>
  </p>
  <div v-else>
    <p class="muted small results-count">
      {{ filtered.length }} {{ filtered.length === 1 ? "pessoa" : "pessoas" }}
    </p>
    <div class="people-grid">
      <RouterLink
        v-for="p in filtered"
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
        <div v-if="p.graduation_years?.length || p.classes?.length" class="meta-tags">
          <span v-for="y in p.graduation_years" :key="`y-${y}`" class="tag tag-year">{{ y }}</span>
          <span v-for="c in p.classes" :key="`c-${c}`" class="tag tag-class">{{ c }}</span>
        </div>
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 1rem; }
.page-header h1 { margin: 0; }
.page-header p { margin: 0.2rem 0 0; }

.filters {
  margin-bottom: 1.25rem;
  padding: 1rem;
}
.filter-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  align-items: end;
}
.filter-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--muted);
}
.clear-btn {
  align-self: stretch;
}
@media (min-width: 640px) {
  .filter-grid {
    grid-template-columns: 2fr 1fr 1fr max-content;
  }
}

.results-count { margin: 0 0 0.6rem; }

.people-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.75rem;
}
.person-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.45rem;
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

.meta-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.25rem;
  margin-top: 0.2rem;
}
.tag {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 99px;
  letter-spacing: 0.02em;
}
.tag-year {
  background: rgba(14, 109, 194, 0.12);
  color: var(--marista-blue);
}
.tag-class {
  background: rgba(247, 201, 72, 0.18);
  color: #8a6913;
}
</style>
