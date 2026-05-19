<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import CenteredNotice from "@/components/CenteredNotice.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import {
  songsModerationApi,
  type ModerationCounts,
  type Song,
} from "@/services/api";
import { useNotifyStore } from "@/stores/notify";

const notify = useNotifyStore();

type Status = "pending" | "approved" | "rejected";
type ConfirmAction =
  | { kind: "approve"; ids: string[]; note?: string }
  | { kind: "reject"; ids: string[]; note?: string }
  | { kind: "delete"; ids: string[] };

const status = ref<Status>("pending");
const items = ref<Song[]>([]);
const counts = ref<ModerationCounts>({ pending: 0, approved: 0, rejected: 0 });
const loading = ref(true);
const busy = ref(false);

const selected = ref<Set<string>>(new Set());
function toggleSelected(id: string) {
  const s = new Set(selected.value);
  if (s.has(id)) s.delete(id);
  else s.add(id);
  selected.value = s;
}
const allSelectedOnPage = computed(
  () => items.value.length > 0 && items.value.every((i) => selected.value.has(i.id)),
);
function selectAllPage() {
  const s = new Set(selected.value);
  for (const i of items.value) s.add(i.id);
  selected.value = s;
}
function clearSelection() {
  selected.value = new Set();
}

const confirmOpen = ref(false);
const confirmAction = ref<ConfirmAction | null>(null);
const confirmConfig = computed(() => {
  const a = confirmAction.value;
  if (!a) return null;
  const count = a.ids.length;
  if (a.kind === "approve") {
    return {
      title: count === 1 ? "Aprovar música?" : `Aprovar ${count} músicas?`,
      message:
        count === 1
          ? "Essa música vai aparecer no mural público e na trilha do kiosk."
          : `Essas ${count} músicas vão aparecer no mural público e na trilha do kiosk.`,
      variant: "default" as const,
      confirmLabel: count === 1 ? "Aprovar" : `Aprovar ${count}`,
      typeToConfirm: "",
      details: [] as string[],
    };
  }
  if (a.kind === "reject") {
    return {
      title: count === 1 ? "Rejeitar música?" : `Rejeitar ${count} músicas?`,
      message:
        count === 1
          ? "A música será escondida do mural e do kiosk. Pode ser reaprovada depois."
          : `${count} músicas serão escondidas do mural e do kiosk. Podem ser reaprovadas depois.`,
      variant: "default" as const,
      confirmLabel: count === 1 ? "Rejeitar" : `Rejeitar ${count}`,
      typeToConfirm: "",
      details: [] as string[],
    };
  }
  return {
    title:
      count === 1 ? "Apagar música definitivamente?" : `Apagar ${count} músicas definitivamente?`,
    message: "",
    variant: "danger" as const,
    confirmLabel: count === 1 ? "Apagar" : `Apagar ${count}`,
    typeToConfirm: "APAGAR",
    details: [
      `Remove ${count === 1 ? "a música" : "as músicas"} do banco.`,
      "Esta ação não pode ser desfeita.",
    ],
  };
});

function openConfirm(a: ConfirmAction) {
  confirmAction.value = a;
  confirmOpen.value = true;
}
function closeConfirm() {
  if (busy.value) return;
  confirmOpen.value = false;
  confirmAction.value = null;
}

async function runConfirm() {
  const a = confirmAction.value;
  if (!a) return;
  busy.value = true;
  try {
    if (a.kind === "approve") {
      if (a.ids.length === 1) await songsModerationApi.approve(a.ids[0], a.note);
      else await songsModerationApi.bulkApprove(a.ids, a.note);
    } else if (a.kind === "reject") {
      if (a.ids.length === 1) await songsModerationApi.reject(a.ids[0], a.note);
      else await songsModerationApi.bulkReject(a.ids, a.note);
    } else {
      await songsModerationApi.bulkDelete(a.ids);
    }
    selected.value = new Set();
    confirmOpen.value = false;
    confirmAction.value = null;
    // Refetch a página atual em vez de só filtrar local — assim quando você
    // processa o lote inteiro, a próxima leva de itens entra no lugar.
    await Promise.all([loadCounts(), load()]);
  } catch (e) {
    notify.error("Erro ao processar", e);
  } finally {
    busy.value = false;
  }
}

function approveOne(item: Song) {
  openConfirm({ kind: "approve", ids: [item.id] });
}
function rejectOne(item: Song) {
  openConfirm({ kind: "reject", ids: [item.id] });
}
function deleteOne(item: Song) {
  openConfirm({ kind: "delete", ids: [item.id] });
}
function bulkApprove() {
  openConfirm({ kind: "approve", ids: Array.from(selected.value) });
}
function bulkReject() {
  openConfirm({ kind: "reject", ids: Array.from(selected.value) });
}
function bulkDelete() {
  openConfirm({ kind: "delete", ids: Array.from(selected.value) });
}

async function loadCounts() {
  try {
    counts.value = await songsModerationApi.counts();
  } catch {
    /* silent */
  }
}
async function load() {
  loading.value = true;
  selected.value = new Set();
  try {
    items.value = await songsModerationApi.list(status.value, 100, 0);
  } finally {
    loading.value = false;
  }
}

const fmt = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
const currentTitle = computed(() => {
  if (status.value === "pending") return "Músicas aguardando aprovação";
  if (status.value === "approved") return "Músicas aprovadas";
  return "Músicas rejeitadas";
});

watch(status, load);
onMounted(async () => {
  await Promise.all([loadCounts(), load()]);
});
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Músicas</h1>
      <p class="muted">Aprove músicas enviadas por usuários antes de aparecerem no mural e no kiosk.</p>
    </div>
  </header>

  <div class="tabs">
    <button :class="{ active: status === 'pending' }" @click="status = 'pending'">
      Pendentes
      <span class="badge badge-warning">{{ counts.pending }}</span>
    </button>
    <button :class="{ active: status === 'approved' }" @click="status = 'approved'">
      Aprovadas
      <span class="badge">{{ counts.approved }}</span>
    </button>
    <button :class="{ active: status === 'rejected' }" @click="status = 'rejected'">
      Rejeitadas
      <span class="badge">{{ counts.rejected }}</span>
    </button>
  </div>

  <div v-if="items.length" class="select-bar">
    <label class="select-all">
      <input
        type="checkbox"
        :checked="allSelectedOnPage"
        :indeterminate.prop="selected.size > 0 && !allSelectedOnPage"
        @change="allSelectedOnPage ? clearSelection() : selectAllPage()"
      />
      <span>
        <template v-if="selected.size === 0">Selecionar todas da página</template>
        <template v-else>{{ selected.size }} selecionada{{ selected.size === 1 ? "" : "s" }}</template>
      </span>
    </label>
    <div v-if="selected.size > 0" class="bulk-actions">
      <button v-if="status === 'pending'" class="button small" @click="bulkApprove">✓ Aprovar</button>
      <button
        v-if="status === 'pending' || status === 'approved'"
        class="button small secondary"
        @click="bulkReject"
      >✕ Rejeitar</button>
      <button v-if="status === 'rejected'" class="button small" @click="bulkApprove">Reaprovar</button>
      <button v-if="status === 'rejected'" class="button small danger" @click="bulkDelete">
        🗑 Apagar definitivamente
      </button>
      <button class="button small ghost" @click="clearSelection">Limpar</button>
    </div>
  </div>

  <h3 class="section-title">{{ currentTitle }}</h3>

  <CenteredNotice v-if="loading" variant="loading">Carregando…</CenteredNotice>
  <CenteredNotice v-else-if="!items.length" variant="empty">
    <template v-if="status === 'pending'">🎉 Nada na fila. Tudo aprovado!</template>
    <template v-else>Nenhuma música.</template>
  </CenteredNotice>

  <div v-else class="list">
    <article
      v-for="item in items"
      :key="item.id"
      class="card-item"
      :class="{ selected: selected.has(item.id) }"
    >
      <label class="card-check" @click.stop>
        <input
          type="checkbox"
          :checked="selected.has(item.id)"
          @change="toggleSelected(item.id)"
        />
      </label>

      <a
        :href="item.watch_url"
        target="_blank"
        rel="noopener"
        class="thumb-wrap"
        :aria-label="item.title || 'Abrir no YouTube'"
      >
        <img
          v-if="item.thumbnail_url"
          :src="item.thumbnail_url"
          :alt="item.title || ''"
          loading="lazy"
        />
        <div v-else class="thumb-fallback">🎵</div>
      </a>

      <div class="info">
        <strong class="title">{{ item.title || "Vídeo do YouTube" }}</strong>
        <span v-if="item.channel" class="muted small">{{ item.channel }}</span>
        <p v-if="item.caption" class="caption">"{{ item.caption }}"</p>

        <div class="meta-row">
          <span v-if="item.user_email" class="tag">{{ item.user_email }}</span>
          <span v-if="item.user_graduation_year" class="tag">
            {{ item.user_graduation_year }}
            <template v-if="item.user_class_letter">— {{ item.user_class_letter }}</template>
          </span>
          <span class="muted small">{{ fmt(item.created_at) }}</span>
        </div>
        <p v-if="item.moderation_note" class="muted small note">
          <em>{{ item.moderation_note }}</em>
        </p>

        <div class="actions">
          <template v-if="status === 'pending'">
            <button class="button small" @click="approveOne(item)">✓ Aprovar</button>
            <button class="button small secondary" @click="rejectOne(item)">✕ Rejeitar</button>
          </template>
          <template v-else-if="status === 'rejected'">
            <button class="button small" @click="approveOne(item)">Reaprovar</button>
            <button class="button small danger" @click="deleteOne(item)">🗑 Apagar</button>
          </template>
          <template v-else>
            <button class="button small secondary" @click="rejectOne(item)">Remover de público</button>
          </template>
        </div>
      </div>
    </article>
  </div>

  <ConfirmDialog
    v-if="confirmConfig"
    :open="confirmOpen"
    :title="confirmConfig.title"
    :message="confirmConfig.message"
    :variant="confirmConfig.variant"
    :confirm-label="confirmConfig.confirmLabel"
    :type-to-confirm="confirmConfig.typeToConfirm"
    :details="confirmConfig.details"
    :busy="busy"
    @close="closeConfirm"
    @confirm="runConfirm"
  />
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
  background: rgba(247, 201, 72, 0.25);
  color: #8a6913;
}

.select-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.85rem;
  margin: 0 -0.5rem 0.75rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  flex-wrap: wrap;
}
.select-all {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.9rem;
  color: var(--text);
  cursor: pointer;
  user-select: none;
}
.select-all input { width: 18px; height: 18px; accent-color: var(--marista-blue); }
.bulk-actions { display: flex; gap: 0.4rem; flex-wrap: wrap; }

.section-title { margin: 0 0 1rem; font-size: 1rem; color: var(--muted); font-weight: 600; }

.list { display: flex; flex-direction: column; gap: 0.6rem; }
.card-item {
  position: relative;
  display: grid;
  grid-template-columns: 36px 140px 1fr;
  gap: 0.75rem;
  align-items: stretch;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.7rem 0.85rem;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.card-item.selected {
  border-color: var(--marista-blue);
  box-shadow: 0 0 0 1px var(--marista-blue);
}
.card-check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.card-check input {
  width: 20px; height: 20px;
  accent-color: var(--marista-blue);
  cursor: pointer;
  margin: 0;
}
.thumb-wrap {
  display: block;
  aspect-ratio: 16 / 9;
  width: 140px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-strong);
}
.thumb-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb-fallback {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  font-size: 2rem;
  color: var(--muted);
}
.info {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 0;
}
.title {
  font-size: 0.95rem;
  color: var(--marista-navy);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.caption {
  margin: 0.1rem 0;
  font-style: italic;
  color: var(--text);
  font-size: 0.88rem;
}
.meta-row { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
.tag {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.5rem;
  border-radius: 99px;
  background: var(--surface-strong);
  color: var(--text);
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
.button.small.danger { background: var(--error); color: white; }
.button.small.danger:hover:not(:disabled) { background: #b32f2f; }
.button.small.ghost {
  background: transparent;
  color: var(--muted);
  border: 1px solid var(--border);
}
.button.small.ghost:hover { color: var(--text); background: var(--surface-strong); }

@media (max-width: 600px) {
  .card-item {
    grid-template-columns: 36px 1fr;
    grid-template-areas:
      "check thumb"
      "info  info";
  }
  .card-check { grid-area: check; }
  .thumb-wrap { grid-area: thumb; width: 100%; }
  .info { grid-area: info; }
}
</style>
