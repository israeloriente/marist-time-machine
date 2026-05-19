<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import CenteredNotice from "@/components/CenteredNotice.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import MediaPreview from "@/components/MediaPreview.vue";
import {
  moderationApi,
  type ModerationCounts,
  type PhotoModerationItem,
} from "@/services/api";
import { useNotifyStore } from "@/stores/notify";

const notify = useNotifyStore();

type Status = "pending" | "approved" | "rejected";
type ConfirmAction =
  | { kind: "approve"; ids: string[]; note?: string }
  | { kind: "reject"; ids: string[]; note?: string }
  | { kind: "delete"; ids: string[] };

const status = ref<Status>("pending");
const items = ref<PhotoModerationItem[]>([]);
const counts = ref<ModerationCounts>({ pending: 0, approved: 0, rejected: 0 });
const loading = ref(true);
const busy = ref(false);
const lightboxIdx = ref<number | null>(null);

// Selection
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

// Confirm dialog state
const confirmOpen = ref(false);
const confirmAction = ref<ConfirmAction | null>(null);
const confirmConfig = computed(() => {
  const a = confirmAction.value;
  if (!a) return null;
  const count = a.ids.length;
  if (a.kind === "approve") {
    return {
      title: count === 1 ? "Aprovar foto?" : `Aprovar ${count} fotos?`,
      message:
        count === 1
          ? "Essa foto vai ficar disponível em buscas, kiosk e moderação por nome."
          : `Essas ${count} fotos vão ficar disponíveis em buscas, kiosk e moderação por nome.`,
      variant: "default" as const,
      confirmLabel: count === 1 ? "Aprovar" : `Aprovar ${count}`,
      typeToConfirm: "",
      details: [] as string[],
    };
  }
  if (a.kind === "reject") {
    return {
      title: count === 1 ? "Rejeitar foto?" : `Rejeitar ${count} fotos?`,
      message:
        count === 1
          ? "A foto será escondida de buscas/kiosk. Pode ser reaprovada depois."
          : `${count} fotos serão escondidas de buscas/kiosk. Podem ser reaprovadas depois.`,
      variant: "default" as const,
      confirmLabel: count === 1 ? "Rejeitar" : `Rejeitar ${count}`,
      typeToConfirm: "",
      details: [] as string[],
    };
  }
  // delete
  const facesTotal = items.value
    .filter((i) => a.ids.includes(i.id))
    .reduce((s, i) => s + i.face_count, 0);
  return {
    title:
      count === 1 ? "Apagar foto definitivamente?" : `Apagar ${count} fotos definitivamente?`,
    message: "",
    variant: "danger" as const,
    confirmLabel: count === 1 ? "Apagar" : `Apagar ${count}`,
    typeToConfirm: "APAGAR",
    details: [
      `Remove ${count === 1 ? "a foto" : "as fotos"} do banco e do storage Hetzner.`,
      `${facesTotal} ${facesTotal === 1 ? "rosto detectado" : "rostos detectados"} também ${
        facesTotal === 1 ? "será apagado" : "serão apagados"
      }.`,
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
      if (a.ids.length === 1) await moderationApi.approve(a.ids[0], a.note);
      else await moderationApi.bulkApprove(a.ids, a.note);
    } else if (a.kind === "reject") {
      if (a.ids.length === 1) await moderationApi.reject(a.ids[0], a.note);
      else await moderationApi.bulkReject(a.ids, a.note);
    } else {
      // delete
      if (a.ids.length === 1) await moderationApi.deleteForever(a.ids[0]);
      else await moderationApi.bulkDelete(a.ids);
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

// ----- Actions -----

function approveOne(item: PhotoModerationItem) {
  openConfirm({ kind: "approve", ids: [item.id] });
}
function rejectOne(item: PhotoModerationItem) {
  openConfirm({ kind: "reject", ids: [item.id] });
}
function deleteOne(item: PhotoModerationItem) {
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

// ----- Loading -----

async function loadCounts() {
  try {
    counts.value = await moderationApi.counts();
  } catch {
    /* silent */
  }
}
async function load() {
  loading.value = true;
  selected.value = new Set();
  try {
    items.value = await moderationApi.list(status.value, 100, 0);
  } finally {
    loading.value = false;
  }
}

const fmt = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
const currentTitle = computed(() => {
  if (status.value === "pending") return "Fotos aguardando aprovação";
  if (status.value === "approved") return "Fotos aprovadas";
  return "Fotos rejeitadas";
});

watch(status, load);
onMounted(async () => {
  await Promise.all([loadCounts(), load()]);
});
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Fotos</h1>
      <p class="muted">Modere o conteúdo enviado pelos usuários antes de publicar.</p>
    </div>
  </header>

  <!-- Tabs by status -->
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

  <!-- Selection bar -->
  <div v-if="items.length" class="select-bar">
    <label class="select-all">
      <input
        type="checkbox"
        :checked="allSelectedOnPage"
        :indeterminate.prop="selected.size > 0 && !allSelectedOnPage"
        @change="allSelectedOnPage ? clearSelection() : selectAllPage()"
      />
      <span>
        <template v-if="selected.size === 0">Selecionar todos da página</template>
        <template v-else>{{ selected.size }} selecionada{{ selected.size === 1 ? "" : "s" }}</template>
      </span>
    </label>
    <div v-if="selected.size > 0" class="bulk-actions">
      <button v-if="status === 'pending'" class="button small" @click="bulkApprove">
        ✓ Aprovar
      </button>
      <button
        v-if="status === 'pending' || status === 'approved'"
        class="button small secondary"
        @click="bulkReject"
      >
        ✕ Rejeitar
      </button>
      <button v-if="status === 'rejected'" class="button small" @click="bulkApprove">
        Reaprovar
      </button>
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
    <template v-else>Nenhuma foto.</template>
  </CenteredNotice>

  <div v-else class="grid">
    <article
      v-for="(item, idx) in items"
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

      <button class="thumb-btn" type="button" @click="lightboxIdx = idx">
        <MediaPreview
          :src="item.signed_url"
          :thumb-src="item.thumb_signed_url"
          :media-type="item.media_type"
          :alt="item.id"
        />
      </button>

      <div class="info">
        <div class="row">
          <strong class="filename">
            {{ (item.metadata.original_filename as string) || item.id.slice(0, 8) }}
          </strong>
          <span class="muted small">{{ fmt(item.uploaded_at) }}</span>
        </div>
        <div class="meta-row">
          <span v-if="item.uploader_email" class="tag">{{ item.uploader_email }}</span>
          <span v-if="(item.metadata.graduation_year as number)" class="tag">
            {{ item.metadata.graduation_year }}
          </span>
          <span v-if="(item.metadata.class as string)" class="tag">
            Turma {{ item.metadata.class }}
          </span>
          <span class="tag faces">
            {{ item.face_count }} {{ item.face_count === 1 ? "rosto" : "rostos" }}
          </span>
          <span class="tag media">
            {{ item.media_type === "video" ? "vídeo" : "foto" }}
          </span>
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
            <button class="button small danger" @click="deleteOne(item)">
              🗑 Apagar
            </button>
          </template>
          <template v-else>
            <button class="button small secondary" @click="rejectOne(item)">
              Remover de público
            </button>
          </template>
        </div>
      </div>
    </article>
  </div>

  <!-- Lightbox -->
  <transition name="fade">
    <div
      v-if="lightboxIdx !== null && items[lightboxIdx]"
      class="lightbox"
      role="dialog"
      aria-modal="true"
      @click.self="lightboxIdx = null"
    >
      <button class="lightbox-close" @click="lightboxIdx = null">×</button>
      <div class="lightbox-media">
        <video
          v-if="items[lightboxIdx].media_type === 'video'"
          :src="items[lightboxIdx].signed_url"
          controls
          autoplay
          playsinline
        />
        <img v-else :src="items[lightboxIdx].signed_url" alt="" />
      </div>
    </div>
  </transition>

  <!-- Confirmation dialog -->
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
.bulk-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.section-title { margin: 0 0 1rem; font-size: 1rem; color: var(--muted); font-weight: 600; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.85rem;
}
.card-item {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.card-item.selected {
  border-color: var(--marista-blue);
  box-shadow: 0 0 0 1px var(--marista-blue);
}

.card-check {
  position: absolute;
  top: 0.6rem;
  left: 0.6rem;
  z-index: 3;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 6px;
  padding: 0.25rem;
  cursor: pointer;
  display: inline-flex;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}
.card-check input {
  width: 20px;
  height: 20px;
  accent-color: var(--marista-blue);
  cursor: pointer;
  margin: 0;
}

.thumb-btn {
  display: block;
  aspect-ratio: 4 / 3;
  width: 100%;
  padding: 0;
  border: 0;
  background: var(--surface-strong);
  cursor: pointer;
}
.thumb-btn :deep(.media) { border-radius: 0; }

.info {
  padding: 0.85rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  flex: 1;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
}
.filename {
  font-size: 0.9rem;
  color: var(--marista-navy);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.meta-row { display: flex; gap: 0.3rem; flex-wrap: wrap; }
.tag {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.5rem;
  border-radius: 99px;
  background: var(--surface-strong);
  color: var(--text);
}
.tag.faces { background: rgba(14, 109, 194, 0.12); color: var(--marista-blue); }
.tag.media { background: rgba(247, 201, 72, 0.22); color: #8a6913; }
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
.button.small.danger:hover:not(:disabled) {
  background: #b32f2f;
}
.button.small.ghost {
  background: transparent;
  color: var(--muted);
  border: 1px solid var(--border);
}
.button.small.ghost:hover { color: var(--text); background: var(--surface-strong); }

/* Lightbox */
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4vh 4vw;
}
.lightbox-media {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
}
.lightbox-media img, .lightbox-media video {
  max-width: 100%; max-height: 100%;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.lightbox-close {
  position: absolute;
  top: 1rem; right: 1rem;
  width: 44px; height: 44px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  font-size: 1.5rem;
  cursor: pointer;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
