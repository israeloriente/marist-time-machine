<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  dedupePhotos,
  moderationApi,
  peopleApi,
  regenerateVideoThumbnails,
  suggestionsApi,
  type ClusterStats,
  type ModerationCounts,
  type ReclusterStatus,
} from "@/services/api";

const stats = ref<ClusterStats | null>(null);
const status = ref<ReclusterStatus | null>(null);
const suggestionsPending = ref<number>(0);
const photoCounts = ref<ModerationCounts>({ pending: 0, approved: 0, rejected: 0 });
const reclusterBusy = ref(false);
const dedupeBusy = ref(false);
const thumbsBusy = ref(false);

async function load() {
  const [s, st, sug, pc] = await Promise.all([
    peopleApi.stats().catch(() => null),
    peopleApi.status().catch(() => null),
    suggestionsApi.pendingByTarget().catch(() => []),
    moderationApi.counts().catch(() => ({ pending: 0, approved: 0, rejected: 0 })),
  ]);
  stats.value = s;
  status.value = st;
  suggestionsPending.value = sug.length;
  photoCounts.value = pc;
}

const clusteredPct = computed(() => {
  if (!stats.value || stats.value.faces_total === 0) return 0;
  return Math.round((stats.value.faces_clustered / stats.value.faces_total) * 100);
});

const fmt = (iso: string | null | undefined) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
};

async function runRecluster() {
  if (
    !confirm(
      "Reagrupar agora?\n\nPessoas com nome serão preservadas (junto com seus rostos).\n" +
        "Pessoas sem nome serão refeitas a partir dos rostos não atribuídos.",
    )
  ) return;
  reclusterBusy.value = true;
  try {
    const r = await peopleApi.recluster(true);
    alert(`Concluído.\n${r.faces_assigned} rostos atribuídos. ${r.people_created} pessoas criadas.`);
    await load();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    reclusterBusy.value = false;
  }
}

async function runRegenThumbs() {
  if (!confirm("Gerar thumbnails dos vídeos que ainda não têm? Pode levar alguns minutos.")) return;
  thumbsBusy.value = true;
  try {
    const r = await regenerateVideoThumbnails();
    alert(
      `Concluído.\n${r.videos_visited} vídeos sem thumb.\n${r.thumbnails_generated} gerados.\n${r.errors} erros.`,
    );
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    thumbsBusy.value = false;
  }
}

async function runDedupe() {
  if (!confirm("Procurar e remover fotos duplicadas? Pode levar alguns minutos.")) return;
  dedupeBusy.value = true;
  try {
    const r = await dedupePhotos();
    alert(
      `Concluído.\n${r.photos_visited} fotos vistas.\n${r.duplicates_removed} duplicatas removidas.\n${r.hashed} novas com hash.\n${r.errors} erros.`,
    );
    await load();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    dedupeBusy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Painel</h1>
      <p class="muted">Visão geral do acervo e do reconhecimento facial.</p>
    </div>
    <div class="page-actions">
      <button class="button secondary" :disabled="thumbsBusy" @click="runRegenThumbs">
        {{ thumbsBusy ? "Gerando…" : "Gerar thumbs de vídeo" }}
      </button>
      <button class="button secondary" :disabled="dedupeBusy" @click="runDedupe">
        {{ dedupeBusy ? "Procurando…" : "Remover duplicadas" }}
      </button>
      <button class="button" :disabled="reclusterBusy" @click="runRecluster">
        {{ reclusterBusy ? "Reagrupando…" : "Reagrupar agora" }}
      </button>
    </div>
  </header>

  <!-- KPI cards -->
  <section class="kpis">
    <RouterLink to="/admin/pessoas" class="kpi-card">
      <span class="kpi-label">Pessoas</span>
      <strong class="kpi-value">{{ stats?.people ?? "—" }}</strong>
      <span class="kpi-sub muted">identificadas + anônimas</span>
    </RouterLink>
    <RouterLink to="/admin/nao-atribuidos" class="kpi-card">
      <span class="kpi-label">Rostos clusterizados</span>
      <strong class="kpi-value">
        {{ stats?.faces_clustered ?? "—" }}
        <span class="kpi-frac muted">/ {{ stats?.faces_total ?? "—" }}</span>
      </strong>
      <span class="kpi-sub muted">{{ clusteredPct }}% do total</span>
    </RouterLink>
    <RouterLink to="/admin/fotos" class="kpi-card" :class="{ highlight: photoCounts.pending > 0 }">
      <span class="kpi-label">Fotos pendentes</span>
      <strong class="kpi-value">{{ photoCounts.pending }}</strong>
      <span class="kpi-sub muted">aguardam aprovação</span>
    </RouterLink>
    <RouterLink to="/admin/sugestoes" class="kpi-card highlight">
      <span class="kpi-label">Sugestões pendentes</span>
      <strong class="kpi-value">{{ suggestionsPending }}</strong>
      <span class="kpi-sub muted">aguardam moderação</span>
    </RouterLink>
  </section>

  <!-- Cluster bar -->
  <section v-if="stats" class="card progress-card">
    <div class="progress-head">
      <strong>Progresso do agrupamento</strong>
      <span class="muted small">
        {{ stats.faces_clustered }} de {{ stats.faces_total }} rostos
      </span>
    </div>
    <div class="bar"><div class="bar-fill" :style="{ width: clusteredPct + '%' }"></div></div>
    <p class="muted small" style="margin: 0.5rem 0 0">
      Rostos restantes serão reagrupados automaticamente todo dia às
      <strong>03:00 UTC</strong> ({{ fmt(status?.next_run_at) }}).
    </p>
  </section>

  <!-- Last recluster -->
  <section v-if="status?.last" class="card">
    <strong>Última execução do reagrupamento</strong>
    <dl class="dl">
      <dt>Iniciou</dt><dd>{{ fmt(status.last.started_at) }}</dd>
      <dt>Terminou</dt><dd>{{ fmt(status.last.finished_at) }}</dd>
      <template v-if="status.last.result">
        <dt>Resultado</dt>
        <dd>
          {{ status.last.result.faces_processed }} rostos processados ·
          {{ status.last.result.faces_assigned }} atribuídos ·
          {{ status.last.result.people_created }} novas pessoas
        </dd>
      </template>
      <template v-if="status.last.error">
        <dt>Erro</dt><dd class="error">{{ status.last.error }}</dd>
      </template>
    </dl>
  </section>
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
.page-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }

.kpis {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem 1.1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.15s, transform 0.05s;
}
.kpi-card:hover { border-color: var(--marista-blue); }
.kpi-card.highlight { border-color: rgba(247, 201, 72, 0.5); background: rgba(247, 201, 72, 0.08); }
.kpi-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600; }
.kpi-value { font-size: 1.8rem; line-height: 1.1; color: var(--marista-navy); }
.kpi-frac { font-size: 1rem; font-weight: 500; }
.kpi-sub { font-size: 0.8rem; }

.progress-card { padding: 1rem; margin-bottom: 1rem; }
.progress-head {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.5rem;
}
.bar {
  height: 8px;
  background: var(--surface-strong);
  border-radius: 99px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--marista-blue), var(--marista-blue-soft));
  transition: width 0.3s ease;
}

.dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.4rem 1rem;
  margin: 0.5rem 0 0;
}
.dl dt { color: var(--muted); font-size: 0.85rem; }
.dl dd { margin: 0; font-weight: 600; }
.small { font-size: 0.8rem; }

@media (min-width: 640px) {
  .kpis { grid-template-columns: repeat(3, 1fr); }
}
</style>
