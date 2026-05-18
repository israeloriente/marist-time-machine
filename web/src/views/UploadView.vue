<script setup lang="ts">
import { computed, ref } from "vue";
import { uploadPhoto } from "@/services/api";

interface QueuedFile {
  id: string;
  file: File;
  preview: string;
  kind: "image" | "video";
  status: "pending" | "uploading" | "processing" | "done" | "duplicate" | "error";
  uploadPct: number;     // 0-100 (bytes sent)
  message?: string;
  facesFound?: number;
  abort?: AbortController;
}

const PARALLEL = 3; // simultaneous uploads

const currentYear = new Date().getFullYear();
const graduationYears = Array.from({ length: 111 }, (_, i) => currentYear + 10 - i);
const classes = ["A", "B", "C", "D", "E", "F"];

const graduationYear = ref<number | "">("");
const classLetter = ref<string>("");

const queue = ref<QueuedFile[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const busy = ref(false);

const canSubmit = computed(
  () =>
    !busy.value &&
    queue.value.some((q) => q.status === "pending") &&
    graduationYear.value !== "" &&
    classLetter.value !== "",
);

const stats = computed(() => ({
  total: queue.value.length,
  pending: queue.value.filter((q) => q.status === "pending").length,
  done: queue.value.filter((q) => q.status === "done").length,
  dup: queue.value.filter((q) => q.status === "duplicate").length,
  err: queue.value.filter((q) => q.status === "error").length,
  active: queue.value.filter((q) => q.status === "uploading" || q.status === "processing").length,
}));

const overallPct = computed(() => {
  if (!queue.value.length) return 0;
  const sum = queue.value.reduce((acc, q) => {
    if (q.status === "done" || q.status === "duplicate" || q.status === "error") return acc + 100;
    if (q.status === "processing") return acc + 100; // bytes sent, server-side now
    return acc + q.uploadPct;
  }, 0);
  return Math.round(sum / queue.value.length);
});

function addFiles(files: FileList | File[]) {
  for (const file of Array.from(files)) {
    const kind: "image" | "video" | null = file.type.startsWith("image/")
      ? "image"
      : file.type.startsWith("video/")
        ? "video"
        : null;
    if (!kind) continue;
    queue.value.push({
      id: crypto.randomUUID(),
      file,
      preview: URL.createObjectURL(file),
      kind,
      status: "pending",
      uploadPct: 0,
    });
  }
}

function onFilesPicked(evt: Event) {
  const target = evt.target as HTMLInputElement;
  if (target.files) addFiles(target.files);
  target.value = "";
}

function onDrop(evt: DragEvent) {
  evt.preventDefault();
  dragOver.value = false;
  if (evt.dataTransfer?.files) addFiles(evt.dataTransfer.files);
}

function removeItem(id: string) {
  const idx = queue.value.findIndex((q) => q.id === id);
  if (idx < 0) return;
  const item = queue.value[idx];
  item.abort?.abort();
  URL.revokeObjectURL(item.preview);
  queue.value.splice(idx, 1);
}

function clearDone() {
  queue.value = queue.value.filter((q) => q.status !== "done" && q.status !== "duplicate");
}

async function processOne(item: QueuedFile) {
  item.status = "uploading";
  item.uploadPct = 0;
  item.abort = new AbortController();
  try {
    const res = await uploadPhoto(
      item.file,
      { graduation_year: graduationYear.value, class: classLetter.value },
      {
        onUploadProgress: (pct) => {
          item.uploadPct = pct;
          if (pct >= 100) item.status = "processing";
        },
        signal: item.abort.signal,
      },
    );
    item.uploadPct = 100;
    if (res?.duplicate) {
      item.status = "duplicate";
      item.message = "já existe na base";
      item.facesFound = 0;
    } else {
      item.status = "done";
      item.facesFound = res?.faces?.length ?? 0;
      item.message =
        item.facesFound === 0
          ? "nenhum rosto detectado"
          : `${item.facesFound} ${item.facesFound === 1 ? "rosto" : "rostos"} detectados`;
    }
  } catch (e: any) {
    if (item.abort?.signal.aborted) {
      item.status = "error";
      item.message = "cancelado";
    } else {
      item.status = "error";
      item.message = e.response?.data?.detail ?? e.message ?? String(e);
    }
  } finally {
    item.abort = undefined;
  }
}

async function uploadAll() {
  busy.value = true;

  // Pool: keep PARALLEL concurrent uploads going until queue drains.
  const pending = () => queue.value.filter((q) => q.status === "pending");
  const inflight = new Set<Promise<void>>();

  while (true) {
    const next = pending().slice(0, PARALLEL - inflight.size);
    if (!next.length && !inflight.size) break;
    for (const item of next) {
      const p = processOne(item).finally(() => inflight.delete(p));
      inflight.add(p);
    }
    if (inflight.size) await Promise.race(inflight);
  }

  busy.value = false;
}

function cancelAll() {
  for (const q of queue.value) {
    if (q.status === "uploading" || q.status === "processing") q.abort?.abort();
  }
}
</script>

<template>
  <section class="card">
    <h2>Adicionar ao acervo</h2>
    <p class="muted hide-on-mobile">
      Envie fotos ou vídeos. Para vídeos, um frame representativo é processado
      pra reconhecimento facial.
    </p>

    <!-- Metadata -->
    <div class="form-grid">
      <label>
        <span>Ano de formatura <em>*</em></span>
        <select v-model.number="graduationYear" class="input" required>
          <option value="" disabled>Selecione</option>
          <option v-for="y in graduationYears" :key="y" :value="y">{{ y }}</option>
        </select>
      </label>
      <label>
        <span>Turma <em>*</em></span>
        <select v-model="classLetter" class="input" required>
          <option value="" disabled>Selecione</option>
          <option v-for="c in classes" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
    </div>

    <!-- Drop zone -->
    <div
      class="dropzone"
      :class="{ over: dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop="onDrop"
      @click="fileInput?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        accept="image/*,video/*"
        multiple
        hidden
        @change="onFilesPicked"
      />
      <div class="dropzone-inner">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 13V3"/><path d="m7 8 5-5 5 5"/><path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6"/>
        </svg>
        <p>
          <strong class="hide-on-mobile">Arraste fotos ou vídeos</strong>
          <strong class="show-on-mobile">Toque para escolher</strong>
          <span class="muted hide-on-mobile"> ou clique pra escolher</span>
        </p>
        <p class="muted small">JPG · PNG · WebP · HEIC · MP4 · MOV · WebM</p>
      </div>
    </div>

    <!-- Overall progress -->
    <div v-if="queue.length" class="overall">
      <div class="overall-bar">
        <div class="overall-fill" :style="{ width: overallPct + '%' }"></div>
      </div>
      <div class="overall-meta">
        <span>{{ overallPct }}%</span>
        <span class="muted">
          {{ stats.done }}/{{ stats.total }} concluídas
          <span v-if="stats.dup">· {{ stats.dup }} duplicada{{ stats.dup === 1 ? "" : "s" }}</span>
          <span v-if="stats.err" class="error">· {{ stats.err }} erro</span>
        </span>
      </div>
    </div>

    <!-- Queue -->
    <ul v-if="queue.length" class="queue-list">
      <li v-for="q in queue" :key="q.id" :class="['queue-item', q.status]">
        <div class="thumb">
          <img v-if="q.kind === 'image'" :src="q.preview" alt="" />
          <video v-else :src="q.preview" muted playsinline preload="metadata" />
          <span class="badge">{{ q.kind === "video" ? "vídeo" : "foto" }}</span>
        </div>
        <div class="info">
          <div class="row">
            <strong class="filename">{{ q.file.name }}</strong>
            <button
              v-if="q.status === 'pending' || q.status === 'uploading' || q.status === 'processing'"
              type="button"
              class="remove"
              :aria-label="q.status === 'pending' ? 'remover' : 'cancelar'"
              @click="removeItem(q.id)"
            >✕</button>
          </div>
          <span class="muted small">{{ (q.file.size / 1024 / 1024).toFixed(1) }} MB</span>

          <!-- Per-item progress bar -->
          <div v-if="q.status !== 'done' && q.status !== 'duplicate' && q.status !== 'error'" class="bar">
            <div
              class="bar-fill"
              :class="{ indeterminate: q.status === 'processing' }"
              :style="{ width: q.status === 'processing' ? '100%' : q.uploadPct + '%' }"
            ></div>
          </div>

          <span class="status-text">
            <template v-if="q.status === 'pending'">Aguardando…</template>
            <template v-else-if="q.status === 'uploading'">{{ q.uploadPct }}%</template>
            <template v-else-if="q.status === 'processing'">Analisando rostos…</template>
            <template v-else-if="q.status === 'done'">✓ {{ q.message }}</template>
            <template v-else-if="q.status === 'duplicate'">⏭ {{ q.message }}</template>
            <template v-else-if="q.status === 'error'" class="error">✗ {{ q.message }}</template>
          </span>
        </div>
      </li>
    </ul>

    <!-- Sticky action bar (mobile-friendly) -->
    <div class="actions">
      <button class="button" :disabled="!canSubmit" @click="uploadAll">
        <template v-if="busy">Enviando {{ stats.active }} de {{ stats.total }}…</template>
        <template v-else>Enviar {{ stats.pending || "" }} {{ stats.pending === 1 ? "arquivo" : "arquivos" }}</template>
      </button>
      <button
        v-if="busy"
        type="button"
        class="button secondary"
        @click="cancelAll"
      >
        Cancelar
      </button>
      <button
        v-else-if="stats.done"
        type="button"
        class="button secondary"
        @click="clearDone"
      >
        Limpar enviados
      </button>
    </div>
  </section>
</template>

<style scoped>
.card {
  padding: 1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin: 1rem 0 1rem;
}
.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
  color: var(--muted);
}
.form-grid em {
  color: var(--accent);
  font-style: normal;
}

.dropzone {
  border: 2px dashed var(--border-strong);
  border-radius: 12px;
  padding: 1.5rem 1rem;
  text-align: center;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  background: var(--surface-strong);
  color: var(--text);
}
.dropzone:hover, .dropzone.over {
  border-color: var(--marista-blue);
  background: rgba(14, 109, 194, 0.06);
}
.dropzone-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: var(--text);
}
.dropzone p { margin: 0; }
.small { font-size: 0.8rem; }

.overall {
  margin-top: 1rem;
  margin-bottom: 0.5rem;
}
.overall-bar {
  height: 6px;
  background: var(--surface-strong);
  border-radius: 99px;
  overflow: hidden;
}
.overall-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--marista-blue), var(--marista-blue-soft));
  transition: width 0.3s ease;
}
.overall-meta {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 0.4rem;
  font-size: 0.85rem;
}

.queue-list {
  list-style: none;
  padding: 0;
  margin: 0.75rem 0 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.queue-item {
  display: flex;
  align-items: stretch;
  gap: 0.75rem;
  padding: 0.6rem;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
}
.thumb {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-strong);
  flex-shrink: 0;
}
.thumb img, .thumb video {
  width: 100%; height: 100%; object-fit: cover;
}
.thumb .badge {
  position: absolute; bottom: 2px; right: 2px;
  background: var(--marista-navy); color: var(--marista-yellow);
  font-size: 0.6rem; padding: 1px 5px; border-radius: 4px;
  font-weight: 700; letter-spacing: 0.02em;
}
.info {
  display: flex; flex-direction: column;
  gap: 0.25rem; flex: 1; min-width: 0;
}
.info .row {
  display: flex; justify-content: space-between;
  align-items: center; gap: 0.5rem;
}
.filename {
  overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; font-size: 0.9rem;
}
.bar {
  height: 4px;
  background: var(--surface-strong);
  border-radius: 99px;
  overflow: hidden;
  margin-top: 0.15rem;
}
.bar-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.2s ease;
}
.bar-fill.indeterminate {
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite linear;
}
@keyframes shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -200% 0; }
}
.status-text { font-size: 0.8rem; color: var(--muted); }
.queue-item.done .status-text { color: #4ade80; }
.queue-item.done { border-color: rgba(74, 222, 128, 0.4); }
.queue-item.duplicate { border-color: rgba(170, 182, 207, 0.4); opacity: 0.7; }
.queue-item.duplicate .status-text { color: var(--muted); }
.queue-item.error .status-text,
.queue-item.error { border-color: rgba(255, 107, 107, 0.5); }
.queue-item.error .status-text { color: var(--error); }
.remove {
  background: none; border: none;
  color: var(--muted); cursor: pointer;
  font-size: 1rem; padding: 4px 8px;
  border-radius: 6px;
}
.remove:hover { background: var(--surface-strong); color: var(--text); }

.actions {
  position: sticky;
  bottom: 0;
  margin-top: 1rem;
  padding-top: 0.75rem;
  background: linear-gradient(to top, var(--bg) 65%, transparent);
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.actions .button {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
}

.show-on-mobile { display: inline; }
.hide-on-mobile { display: none; }

@media (min-width: 640px) {
  .card { padding: 1.5rem; }
  .form-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
  .dropzone { padding: 2rem 1rem; }
  .show-on-mobile { display: none; }
  .hide-on-mobile { display: inline; }
  .actions { position: static; background: none; }
  .actions .button { flex: 0 0 auto; }
}
</style>
