<script setup lang="ts">
import { onMounted, ref } from "vue";
import CenteredNotice from "@/components/CenteredNotice.vue";
import { peopleApi, type ReclusterStatus } from "@/services/api";

const status = ref<ReclusterStatus | null>(null);
const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    status.value = await peopleApi.status();
  } finally {
    loading.value = false;
  }
}

const fmt = (iso: string | null | undefined) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
};

onMounted(load);
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Status do sistema</h1>
      <p class="muted">Agendamentos e última execução de jobs do reconhecimento.</p>
    </div>
    <button class="button secondary" @click="load">Atualizar</button>
  </header>

  <CenteredNotice v-if="loading" variant="loading">Carregando…</CenteredNotice>

  <section v-else class="card">
    <h3>Reagrupamento noturno</h3>
    <p class="muted small">
      Roda diariamente às <strong>03:00 UTC</strong> (00:00 BRT). Pessoas com nome não são afetadas.
    </p>

    <dl class="dl">
      <dt>Próxima execução</dt>
      <dd>{{ fmt(status?.next_run_at) }}</dd>

      <template v-if="status?.last">
        <dt>Iniciou</dt><dd>{{ fmt(status.last.started_at) }}</dd>
        <dt>Terminou</dt><dd>{{ fmt(status.last.finished_at) }}</dd>
        <template v-if="status.last.result">
          <dt>Rostos processados</dt><dd>{{ status.last.result.faces_processed }}</dd>
          <dt>Rostos atribuídos</dt><dd>{{ status.last.result.faces_assigned }}</dd>
          <dt>Pessoas criadas</dt><dd>{{ status.last.result.people_created }}</dd>
        </template>
        <template v-if="status.last.error">
          <dt>Erro</dt><dd class="error">{{ status.last.error }}</dd>
        </template>
      </template>
      <template v-else>
        <dt>Última execução</dt><dd class="muted">Ainda não rodou desde o último deploy.</dd>
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

.card { padding: 1.25rem; }
.card h3 { margin: 0 0 0.5rem; }
.dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.5rem 1rem;
  margin: 1rem 0 0;
}
.dl dt { color: var(--muted); font-size: 0.85rem; }
.dl dd { margin: 0; font-weight: 600; }
.small { font-size: 0.8rem; }
</style>
