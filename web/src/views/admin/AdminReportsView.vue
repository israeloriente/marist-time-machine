<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import CenteredNotice from "@/components/CenteredNotice.vue";
import {
  reportsApi,
  type Report,
  type ReportCounts,
} from "@/services/api";
import { useNotifyStore } from "@/stores/notify";

type Status = "pending" | "resolved_removed" | "resolved_rejected";

const notify = useNotifyStore();

const status = ref<Status>("pending");
const items = ref<Report[]>([]);
const counts = ref<ReportCounts>({
  pending: 0,
  resolved_removed: 0,
  resolved_rejected: 0,
});
const loading = ref(true);
const busy = ref<Record<string, boolean>>({});

async function loadCounts() {
  try {
    counts.value = await reportsApi.counts();
  } catch {
    /* silent */
  }
}

async function load() {
  loading.value = true;
  try {
    items.value = await reportsApi.list(status.value, 100, 0);
  } finally {
    loading.value = false;
  }
}

async function resolve(report: Report, action: "remove" | "reject") {
  const confirmed = await notify.confirm({
    title: action === "remove" ? "Apagar mídia?" : "Rejeitar denúncia?",
    message:
      action === "remove"
        ? "A foto/vídeo será apagada do banco e do storage. Não dá pra desfazer."
        : "A denúncia será marcada como rejeitada e a mídia continua no acervo.",
    variant: action === "remove" ? "danger" : "default",
    confirmLabel: action === "remove" ? "Apagar mídia" : "Rejeitar",
  });
  if (!confirmed) return;

  busy.value[report.id] = true;
  try {
    await reportsApi.resolve(report.id, action);
    notify.success(
      action === "remove" ? "Mídia removida." : "Denúncia rejeitada.",
    );
    // Refetch em vez de só filtrar local — assim a próxima denúncia da
    // fila entra no lugar quando você resolve a última visível.
    await Promise.all([loadCounts(), load()]);
  } catch (e) {
    notify.error("Não foi possível resolver a denúncia", e);
  } finally {
    busy.value[report.id] = false;
  }
}

const currentTitle = computed(() => {
  if (status.value === "pending") return "Denúncias aguardando avaliação";
  if (status.value === "resolved_removed") return "Mídias removidas após denúncia";
  return "Denúncias rejeitadas";
});

const fmt = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  });

watch(status, load);
onMounted(async () => {
  await Promise.all([loadCounts(), load()]);
});
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Denúncias</h1>
      <p class="muted">
        Solicitações de remoção feitas por usuários. Avalie e decida.
      </p>
    </div>
  </header>

  <div class="tabs">
    <button :class="{ active: status === 'pending' }" @click="status = 'pending'">
      Pendentes
      <span class="badge badge-warning">{{ counts.pending }}</span>
    </button>
    <button
      :class="{ active: status === 'resolved_removed' }"
      @click="status = 'resolved_removed'"
    >
      Removidas
      <span class="badge">{{ counts.resolved_removed }}</span>
    </button>
    <button
      :class="{ active: status === 'resolved_rejected' }"
      @click="status = 'resolved_rejected'"
    >
      Rejeitadas
      <span class="badge">{{ counts.resolved_rejected }}</span>
    </button>
  </div>

  <h3 class="section-title">{{ currentTitle }}</h3>

  <CenteredNotice v-if="loading" variant="loading">Carregando…</CenteredNotice>
  <CenteredNotice v-else-if="!items.length" variant="empty">
    <template v-if="status === 'pending'">🎉 Nada na fila. Sem denúncias pendentes!</template>
    <template v-else>Nenhuma denúncia.</template>
  </CenteredNotice>

  <div v-else class="list">
    <article v-for="r in items" :key="r.id" class="card-item">
      <a
        v-if="r.photo_thumb_signed_url || r.photo_signed_url"
        :href="r.photo_signed_url ?? '#'"
        target="_blank"
        rel="noopener"
        class="thumb-wrap"
        :aria-label="'Ver mídia denunciada'"
      >
        <img
          :src="r.photo_thumb_signed_url ?? r.photo_signed_url ?? ''"
          :alt="''"
          loading="lazy"
        />
      </a>
      <div v-else class="thumb-fallback">🚩</div>

      <div class="info">
        <div class="row">
          <strong class="reason">{{ r.reason }}</strong>
          <span class="muted small">{{ fmt(r.created_at) }}</span>
        </div>

        <div class="meta-row">
          <span v-if="r.reporter_email" class="tag">
            denunciante: {{ r.reporter_email }}
          </span>
          <span v-if="r.uploader_email" class="tag">
            uploader: {{ r.uploader_email }}
          </span>
          <span v-if="r.contact_info" class="tag">
            contato: {{ r.contact_info }}
          </span>
        </div>

        <p v-if="r.resolution_note" class="muted small note">
          <em>Nota: {{ r.resolution_note }}</em>
        </p>

        <div v-if="status === 'pending'" class="actions">
          <button
            class="button small danger"
            :disabled="!!busy[r.id]"
            @click="resolve(r, 'remove')"
          >
            🗑 Apagar mídia
          </button>
          <button
            class="button small secondary"
            :disabled="!!busy[r.id]"
            @click="resolve(r, 'reject')"
          >
            ✕ Rejeitar denúncia
          </button>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 1rem; }
.page-header h1 { margin: 0; }
.page-header p { margin: 0.2rem 0 0; }

.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.75rem;
  overflow-x: auto;
}
.tabs button {
  background: none;
  border: none;
  color: var(--muted);
  padding: 0.65rem 1rem;
  cursor: pointer;
  font: inherit;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.tabs button.active {
  color: var(--marista-navy);
  border-bottom-color: var(--marista-yellow);
  font-weight: 700;
}
.badge {
  background: rgba(14, 109, 194, 0.12);
  color: var(--marista-blue);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.1rem 0.5rem;
  border-radius: 99px;
}
.badge.badge-warning {
  background: rgba(214, 58, 58, 0.15);
  color: var(--error);
}

.section-title {
  margin: 0 0 1rem;
  font-size: 1rem;
  color: var(--muted);
  font-weight: 600;
}

.list { display: flex; flex-direction: column; gap: 0.6rem; }
.card-item {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 0.85rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.75rem;
  align-items: stretch;
}
.thumb-wrap {
  display: block;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-strong);
}
.thumb-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-strong);
  border-radius: 8px;
  font-size: 2rem;
  color: var(--muted);
  aspect-ratio: 4 / 3;
}

.info {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.reason {
  font-size: 0.95rem;
  color: var(--marista-navy);
  line-height: 1.4;
  white-space: pre-wrap;
}
.meta-row {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.tag {
  background: var(--surface-strong);
  color: var(--text);
  font-size: 0.72rem;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
}
.note { margin: 0.25rem 0 0; }
.small { font-size: 0.78rem; }

.actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-top: auto;
  padding-top: 0.4rem;
}
.button.small {
  min-height: 36px;
  padding: 0.3rem 0.85rem;
  font-size: 0.85rem;
}
.button.small.danger {
  background: var(--error);
  color: white;
}
.button.small.danger:hover:not(:disabled) { background: #b32f2f; }

@media (max-width: 600px) {
  .card-item {
    grid-template-columns: 1fr;
  }
  .thumb-wrap, .thumb-fallback { aspect-ratio: 16 / 9; }
}
</style>
