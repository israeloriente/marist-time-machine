<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import FaceThumb from "@/components/FaceThumb.vue";
import {
  facesApi,
  peopleApi,
  suggestionsApi,
  type AvailableFilters,
  type Face,
  type Person,
} from "@/services/api";

type Mode = "people" | "faces";
const mode = ref<Mode>("people");

const anonymousPeople = ref<Array<Person & { thumb?: Face | null }>>([]);
const orphanFaces = ref<Face[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

// Filters
const year = ref<number | "">("");
const klass = ref<string>("");
const available = ref<AvailableFilters>({ years: [], classes: [] });

// Cache: target id -> pending suggestion count (so contributor sees momentum)
const counts = ref<Record<string, number>>({});

// "Já sugeri" memory in localStorage so the same browser doesn't re-prompt.
const suggested = ref<Record<string, string>>(loadSuggested());

function loadSuggested(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem("mtm.suggested") || "{}");
  } catch {
    return {};
  }
}
function saveSuggested() {
  localStorage.setItem("mtm.suggested", JSON.stringify(suggested.value));
}

async function loadFilters() {
  try {
    available.value = await peopleApi.filters();
  } catch {
    /* silent */
  }
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const filters: { year?: number; class?: string } = {};
    if (year.value !== "") filters.year = year.value;
    if (klass.value) filters.class = klass.value;
    const [allPeople, faces] = await Promise.all([
      peopleApi.list(filters),
      facesApi.unassigned(60, 0, 0.5),
    ]);
    // Only show people without display_name (anonymous clusters).
    const anon = allPeople.filter((p) => !p.display_name);
    // Get one face per anonymous person for the thumbnail.
    await Promise.all(
      anon.map(async (p) => {
        try {
          const f = await peopleApi.faces(p.id);
          (p as Person & { thumb?: Face | null }).thumb = f[0] ?? null;
        } catch {
          (p as Person & { thumb?: Face | null }).thumb = null;
        }
      }),
    );
    anonymousPeople.value = anon;
    orphanFaces.value = faces;

    // Pull pending counts for both lists (best-effort, parallel).
    await Promise.all([
      ...anon.map(async (p) => {
        try {
          const r = await suggestionsApi.count({ person_id: p.id });
          counts.value[p.id] = r.pending;
        } catch {
          counts.value[p.id] = 0;
        }
      }),
      ...faces.map(async (f) => {
        try {
          const r = await suggestionsApi.count({ face_id: f.id });
          counts.value[f.id] = r.pending;
        } catch {
          counts.value[f.id] = 0;
        }
      }),
    ]);
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    loading.value = false;
  }
}

async function suggestForPerson(p: Person) {
  const existing = suggested.value[p.id];
  const prompt_msg = existing
    ? `Você já sugeriu "${existing}" pra essa pessoa.\nMandar outro nome diferente?`
    : "Quem é essa pessoa? Digite o nome completo:";
  const name = prompt(prompt_msg)?.trim();
  if (!name) return;
  try {
    await suggestionsApi.create({ person_id: p.id }, name);
    suggested.value[p.id] = name;
    saveSuggested();
    counts.value[p.id] = (counts.value[p.id] ?? 0) + 1;
  } catch (e: any) {
    const detail = e.response?.data?.detail ?? e.message;
    if (e.response?.status === 409) {
      alert("Você já sugeriu esse nome.");
    } else {
      alert("Erro: " + detail);
    }
  }
}

async function suggestForFace(f: Face) {
  const existing = suggested.value[f.id];
  const prompt_msg = existing
    ? `Você já sugeriu "${existing}" pra esse rosto.\nMandar outro nome diferente?`
    : "Quem é? Digite o nome completo:";
  const name = prompt(prompt_msg)?.trim();
  if (!name) return;
  try {
    await suggestionsApi.create({ face_id: f.id }, name);
    suggested.value[f.id] = name;
    saveSuggested();
    counts.value[f.id] = (counts.value[f.id] ?? 0) + 1;
  } catch (e: any) {
    const detail = e.response?.data?.detail ?? e.message;
    if (e.response?.status === 409) {
      alert("Você já sugeriu esse nome.");
    } else {
      alert("Erro: " + detail);
    }
  }
}

const peopleCount = computed(() => anonymousPeople.value.length);
const facesCount = computed(() => orphanFaces.value.length);
const hasFilters = computed(() => year.value !== "" || klass.value !== "");

function clearFilters() {
  year.value = "";
  klass.value = "";
}

watch([year, klass], load);

onMounted(async () => {
  await Promise.all([loadFilters(), load()]);
});
</script>

<template>
  <section class="card">
    <h2>Ajude a identificar</h2>
    <p class="muted small">
      Reconheceu alguém? Sugira o nome. Suas sugestões passam por revisão antes
      de entrar na base.
    </p>

    <div class="contrib-filters">
      <select v-model.number="year" class="input" aria-label="Ano de formatura">
        <option value="">Todos os anos</option>
        <option v-for="y in available.years" :key="y" :value="y">{{ y }}</option>
      </select>
      <select v-model="klass" class="input" aria-label="Turma">
        <option value="">Todas as turmas</option>
        <option v-for="c in available.classes" :key="c" :value="c">{{ c }}</option>
      </select>
      <button v-if="hasFilters" type="button" class="button secondary clear" @click="clearFilters">
        Limpar
      </button>
    </div>

    <div class="tabs">
      <button :class="{ active: mode === 'people' }" @click="mode = 'people'">
        Pessoas <span class="badge">{{ peopleCount }}</span>
      </button>
      <button :class="{ active: mode === 'faces' }" @click="mode = 'faces'">
        Rostos avulsos <span class="badge">{{ facesCount }}</span>
      </button>
    </div>

    <p v-if="loading" class="muted">Carregando…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <!-- Anonymous people -->
    <div v-else-if="mode === 'people'">
      <p v-if="!peopleCount" class="muted small">
        🎉 Todas as pessoas já têm sugestões ou nome. Volte depois pra mais.
      </p>
      <div v-else class="grid">
        <div v-for="p in anonymousPeople" :key="p.id" class="card-item">
          <FaceThumb
            v-if="p.thumb"
            :src="p.thumb.signed_url"
            :bbox="p.thumb.bbox"
            :size="100"
            :padding="0.3"
          />
          <div v-else class="thumb-placeholder">?</div>
          <span class="muted small">{{ p.face_count }} fotos</span>
          <span v-if="counts[p.id]" class="vote-badge">{{ counts[p.id] }} sugestões</span>
          <span v-if="suggested[p.id]" class="my-suggestion">você: {{ suggested[p.id] }}</span>
          <button class="button small" @click="suggestForPerson(p)">
            {{ suggested[p.id] ? "Sugerir outro" : "Sugerir nome" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Orphan faces -->
    <div v-else>
      <p v-if="!facesCount" class="muted small">Nenhum rosto avulso no momento.</p>
      <div v-else class="grid">
        <div v-for="f in orphanFaces" :key="f.id" class="card-item">
          <FaceThumb :src="f.signed_url" :bbox="f.bbox" :size="100" :padding="0.3" />
          <span class="muted small">{{ (f.detection_score * 100).toFixed(0) }}% certeza</span>
          <span v-if="counts[f.id]" class="vote-badge">{{ counts[f.id] }} sugestões</span>
          <span v-if="suggested[f.id]" class="my-suggestion">você: {{ suggested[f.id] }}</span>
          <button class="button small" @click="suggestForFace(f)">
            {{ suggested[f.id] ? "Sugerir outro" : "Sugerir nome" }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.contrib-filters {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 0.5rem;
  margin: 0.75rem 0 0.25rem;
}
.contrib-filters .clear {
  min-height: 44px;
  padding: 0 1rem;
}
@media (max-width: 480px) {
  .contrib-filters {
    grid-template-columns: 1fr 1fr;
  }
  .contrib-filters .clear { grid-column: 1 / -1; }
}

.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border-strong);
  margin: 1rem 0;
  overflow-x: auto;
}
.tabs button {
  background: none;
  border: none;
  color: var(--muted);
  padding: 0.6rem 0.9rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  font: inherit;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.tabs .badge {
  background: rgba(247, 201, 72, 0.18);
  border-radius: 10px;
  padding: 0.1rem 0.5rem;
  font-size: 0.75rem;
  color: var(--accent);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.6rem;
}
.card-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.7rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  text-align: center;
}
.thumb-placeholder {
  width: 100px; height: 100px;
  border-radius: 8px;
  background: var(--surface-strong);
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 1.8rem;
}
.vote-badge {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
  border-radius: 99px;
  padding: 0.1rem 0.6rem;
  font-size: 0.75rem;
}
.my-suggestion {
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 600;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.button.small {
  min-height: 34px;
  padding: 0.35rem 0.8rem;
  font-size: 0.85rem;
  width: 100%;
}
.small { font-size: 0.75rem; }
</style>
