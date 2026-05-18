<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import FaceThumb from "@/components/FaceThumb.vue";
import {
  dedupePhotos,
  facesApi,
  peopleApi,
  type ClusterStats,
  type Face,
  type Person,
  type ReclusterStatus,
} from "@/services/api";

type Tab = "people" | "unassigned" | "status";
const tab = ref<Tab>("people");

const stats = ref<ClusterStats | null>(null);
const status = ref<ReclusterStatus | null>(null);
const reclusterBusy = ref(false);
const dedupeBusy = ref(false);

const people = ref<Person[]>([]);
const peopleLoading = ref(false);

const unassigned = ref<Face[]>([]);
const unassignedLoading = ref(false);
const unassignedOffset = ref(0);
const unassignedMore = ref(true);

// Cache: person_id -> first face (to render thumb)
const thumbCache = ref<Record<string, Face | null>>({});

async function loadStats() {
  try {
    [stats.value, status.value] = await Promise.all([peopleApi.stats(), peopleApi.status()]);
  } catch (e) {
    console.error(e);
  }
}

async function loadPeople() {
  peopleLoading.value = true;
  try {
    people.value = await peopleApi.list();
    // Fetch one face per person in parallel (for the thumbnail).
    await Promise.all(
      people.value.map(async (p) => {
        if (thumbCache.value[p.id]) return;
        const faces = await peopleApi.faces(p.id);
        thumbCache.value[p.id] = faces[0] ?? null;
      }),
    );
  } finally {
    peopleLoading.value = false;
  }
}

async function loadUnassigned(reset = false) {
  if (reset) {
    unassigned.value = [];
    unassignedOffset.value = 0;
    unassignedMore.value = true;
  }
  if (!unassignedMore.value) return;
  unassignedLoading.value = true;
  try {
    const batch = await facesApi.unassigned(50, unassignedOffset.value, 0.5);
    unassigned.value.push(...batch);
    unassignedOffset.value += batch.length;
    unassignedMore.value = batch.length === 50;
  } finally {
    unassignedLoading.value = false;
  }
}

async function runDedupe() {
  if (
    !confirm(
      "Procurar e remover fotos duplicadas?\n\nIsso percorre todas as fotos sem hash, computa SHA-256 e mescla duplicatas. Pode levar alguns minutos.",
    )
  )
    return;
  dedupeBusy.value = true;
  try {
    const r = await dedupePhotos();
    alert(
      `Concluído.\n${r.photos_visited} fotos vistas.\n${r.duplicates_removed} duplicatas removidas.\n${r.hashed} novas com hash.\n${r.errors} erros.`,
    );
    await loadStats();
    await loadPeople();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    dedupeBusy.value = false;
  }
}

async function runRecluster() {
  if (
    !confirm(
      "Reagrupar agora?\n\nPessoas com nome serão preservadas (junto com seus rostos).\n" +
        "Pessoas sem nome serão refeitas a partir dos rostos não atribuídos.",
    )
  )
    return;
  reclusterBusy.value = true;
  try {
    const res = await peopleApi.recluster(true);
    alert(
      `Reagrupamento concluído.\n${res.faces_assigned} rostos atribuídos. ${res.people_created} pessoas criadas.`,
    );
    await loadStats();
    await loadPeople();
    await loadUnassigned(true);
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    reclusterBusy.value = false;
  }
}

async function promoteToPerson(face: Face) {
  const name = prompt("Nome da nova pessoa (opcional):") ?? "";
  try {
    await facesApi.promote(face.id, name || undefined);
    unassigned.value = unassigned.value.filter((f) => f.id !== face.id);
    await loadStats();
    if (tab.value === "people") await loadPeople();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

async function assignFaceToPerson(face: Face) {
  const ppl = people.value.length ? people.value : await peopleApi.list();
  const choices = ppl
    .map((p, i) => `${i + 1}. ${p.display_name || `Pessoa ${p.id.slice(0, 8)}`} (${p.face_count})`)
    .join("\n");
  const raw = prompt(`Atribuir esse rosto a qual pessoa?\n${choices}\n\nNº:`);
  const idx = raw ? parseInt(raw, 10) - 1 : -1;
  if (idx < 0 || idx >= ppl.length) return;
  try {
    await facesApi.reassign(face.id, ppl[idx].id);
    unassigned.value = unassigned.value.filter((f) => f.id !== face.id);
    await loadStats();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

const fmt = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
};

const clusteredPct = computed(() => {
  if (!stats.value || stats.value.faces_total === 0) return 0;
  return Math.round((stats.value.faces_clustered / stats.value.faces_total) * 100);
});

onMounted(async () => {
  await loadStats();
  await loadPeople();
});

function switchTab(t: Tab) {
  tab.value = t;
  if (t === "unassigned" && !unassigned.value.length) loadUnassigned(true);
}
</script>

<template>
  <section class="card">
    <div class="header-row">
      <h2 style="margin: 0">Admin</h2>
      <div style="display: flex; gap: 0.5rem; flex-wrap: wrap">
        <button class="button secondary" :disabled="dedupeBusy" @click="runDedupe">
          {{ dedupeBusy ? "Procurando…" : "Remover duplicadas" }}
        </button>
        <button class="button secondary" :disabled="reclusterBusy" @click="runRecluster">
          {{ reclusterBusy ? "Reagrupando…" : "Reagrupar agora" }}
        </button>
      </div>
    </div>

    <div v-if="stats" class="stats">
      <div>
        <strong>{{ stats.people }}</strong>
        <span class="muted">pessoas</span>
      </div>
      <div>
        <strong>{{ stats.faces_clustered }}</strong>
        <span class="muted">/ {{ stats.faces_total }} rostos</span>
      </div>
      <div>
        <strong>{{ clusteredPct }}%</strong>
        <span class="muted">agrupados</span>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button :class="{ active: tab === 'people' }" @click="switchTab('people')">Pessoas</button>
      <button :class="{ active: tab === 'unassigned' }" @click="switchTab('unassigned')">
        Não atribuídos
      </button>
      <button :class="{ active: tab === 'status' }" @click="switchTab('status')">Status</button>
    </div>

    <!-- People grid -->
    <div v-if="tab === 'people'">
      <p v-if="peopleLoading" class="muted">Carregando pessoas…</p>
      <p v-else-if="!people.length" class="muted">
        Nenhuma pessoa ainda. Suba mais fotos ou rode "Reagrupar agora".
      </p>
      <div v-else class="people-grid">
        <RouterLink
          v-for="p in people"
          :key="p.id"
          :to="{ name: 'person', params: { id: p.id } }"
          class="person-card"
        >
          <FaceThumb
            v-if="thumbCache[p.id]"
            :src="thumbCache[p.id]!.signed_url"
            :bbox="thumbCache[p.id]!.bbox"
            :size="80"
            :padding="0.3"
          />
          <div v-else class="thumb-placeholder">?</div>
          <div class="person-info">
            <strong>{{ p.display_name || "Sem nome" }}</strong>
            <span class="muted small">{{ p.face_count }} {{ p.face_count === 1 ? "foto" : "fotos" }}</span>
          </div>
        </RouterLink>
      </div>
    </div>

    <!-- Unassigned -->
    <div v-else-if="tab === 'unassigned'">
      <p v-if="unassignedLoading && !unassigned.length" class="muted">Carregando…</p>
      <p v-else-if="!unassigned.length" class="muted">
        🎉 Todos os rostos detectados já estão atribuídos a uma pessoa.
      </p>
      <div v-else class="faces-grid">
        <div v-for="f in unassigned" :key="f.id" class="face-card">
          <FaceThumb :src="f.signed_url" :bbox="f.bbox" :size="80" :padding="0.3" />
          <div class="face-actions">
            <button class="button small" @click="promoteToPerson(f)" title="Nova pessoa">+</button>
            <button class="button small secondary" @click="assignFaceToPerson(f)" title="Atribuir">→</button>
          </div>
          <span class="muted small">{{ (f.detection_score * 100).toFixed(0) }}%</span>
        </div>
      </div>
      <div v-if="unassignedMore" style="text-align: center; margin-top: 1rem">
        <button class="button secondary" :disabled="unassignedLoading" @click="loadUnassigned(false)">
          {{ unassignedLoading ? "Carregando…" : "Carregar mais" }}
        </button>
      </div>
    </div>

    <!-- Status do cron -->
    <div v-else-if="tab === 'status'">
      <p class="muted small" style="margin-bottom: 0.5rem">
        Re-agrupamento automático roda diariamente às 03:00 UTC (00:00 BRT).
      </p>
      <dl v-if="status" class="status-list">
        <dt>Próxima execução</dt>
        <dd>{{ fmt(status.next_run_at) }}</dd>
        <template v-if="status.last">
          <dt>Última execução</dt>
          <dd>{{ fmt(status.last.started_at) }} → {{ fmt(status.last.finished_at) }}</dd>
          <template v-if="status.last.result">
            <dt>Resultado</dt>
            <dd>
              {{ status.last.result.faces_processed }} rostos •
              {{ status.last.result.faces_assigned }} atribuídos •
              {{ status.last.result.people_created }} pessoas criadas
            </dd>
          </template>
          <template v-if="status.last.error">
            <dt>Erro</dt>
            <dd class="error">{{ status.last.error }}</dd>
          </template>
        </template>
      </dl>
    </div>
  </section>
</template>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  padding: 0.75rem;
  background: rgba(11, 31, 58, 0.5);
  border-radius: 10px;
  margin-bottom: 1rem;
}
.stats > div { display: flex; flex-direction: column; }
.stats strong { font-size: 1.4rem; }

.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid #2d4a82;
  margin-bottom: 1rem;
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
}
.tabs button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.people-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.6rem;
}
.person-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem;
  background: rgba(11, 31, 58, 0.4);
  border: 1px solid #1d3258;
  border-radius: 10px;
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.15s;
}
.person-card:hover { border-color: var(--accent); }
.person-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.1rem;
  min-width: 0;
  max-width: 100%;
}
.person-info strong {
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.thumb-placeholder {
  width: 80px; height: 80px;
  border-radius: 8px;
  background: #1a2c4e;
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 1.5rem;
}

.faces-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.6rem;
}
.face-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem;
  background: rgba(11, 31, 58, 0.4);
  border: 1px solid #1d3258;
  border-radius: 10px;
}
.face-actions { display: flex; gap: 0.25rem; }
.button.small {
  min-height: 32px;
  padding: 0.3rem 0.7rem;
  font-size: 0.85rem;
}
.small { font-size: 0.75rem; }

.status-list { margin: 0; }
.status-list dt {
  color: var(--muted);
  font-size: 0.8rem;
  margin-top: 0.6rem;
}
.status-list dd {
  margin: 0.15rem 0 0;
  font-weight: 600;
}
</style>
