<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import MediaPreview from "@/components/MediaPreview.vue";
import {
  moderationApi,
  type ModerationCounts,
  type PhotoModerationItem,
} from "@/services/api";

type Status = "pending" | "approved" | "rejected";

const status = ref<Status>("pending");
const items = ref<PhotoModerationItem[]>([]);
const counts = ref<ModerationCounts>({ pending: 0, approved: 0, rejected: 0 });
const loading = ref(true);
const busyId = ref<string | null>(null);
const lightboxIdx = ref<number | null>(null);

async function loadCounts() {
  try {
    counts.value = await moderationApi.counts();
  } catch {
    /* silent */
  }
}

async function load() {
  loading.value = true;
  try {
    items.value = await moderationApi.list(status.value, 100, 0);
  } finally {
    loading.value = false;
  }
}

async function approve(item: PhotoModerationItem) {
  busyId.value = item.id;
  try {
    await moderationApi.approve(item.id);
    items.value = items.value.filter((p) => p.id !== item.id);
    await loadCounts();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    busyId.value = null;
  }
}

async function reject(item: PhotoModerationItem) {
  const note = prompt("Motivo da rejeição (opcional):") ?? "";
  busyId.value = item.id;
  try {
    await moderationApi.reject(item.id, note.trim() || undefined);
    items.value = items.value.filter((p) => p.id !== item.id);
    await loadCounts();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    busyId.value = null;
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

  <h3 class="section-title">{{ currentTitle }}</h3>

  <p v-if="loading" class="muted">Carregando…</p>
  <p v-else-if="!items.length" class="muted">
    <template v-if="status === 'pending'">🎉 Nada na fila. Tudo aprovado!</template>
    <template v-else>Nenhuma foto.</template>
  </p>

  <div v-else class="grid">
    <article v-for="(item, idx) in items" :key="item.id" class="card-item">
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
          <span class="tag" v-if="item.uploader_email">{{ item.uploader_email }}</span>
          <span class="tag" v-if="(item.metadata.graduation_year as number)">
            {{ item.metadata.graduation_year }}
          </span>
          <span class="tag" v-if="(item.metadata.class as string)">
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
            <button class="button small" :disabled="busyId === item.id" @click="approve(item)">
              ✓ Aprovar
            </button>
            <button
              class="button small secondary"
              :disabled="busyId === item.id"
              @click="reject(item)"
            >
              ✕ Rejeitar
            </button>
          </template>
          <template v-else-if="status === 'rejected'">
            <button class="button small" :disabled="busyId === item.id" @click="approve(item)">
              Reaprovar
            </button>
          </template>
          <template v-else>
            <button
              class="button small secondary"
              :disabled="busyId === item.id"
              @click="reject(item)"
            >
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
</template>

<style scoped>
.page-header { margin-bottom: 1rem; }
.page-header h1 { margin: 0; }
.page-header p { margin: 0.2rem 0 0; }

.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.25rem;
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

.section-title { margin: 0 0 1rem; font-size: 1rem; color: var(--muted); font-weight: 600; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.85rem;
}
.card-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
.meta-row {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
}
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
