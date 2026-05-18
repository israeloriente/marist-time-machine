<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { uploadPhoto } from "@/services/api";

type Status = "pending" | "uploading" | "processing" | "done" | "duplicate" | "error";

interface QueuedFile {
  id: string;
  file: File;
  preview: string;
  kind: "image" | "video";
  status: Status;
  uploadPct: number;
  message?: string;
  facesFound?: number;
  abort?: AbortController;
}

const PARALLEL = 3;
const MAX_PREVIEW = 300; // beyond this, items still upload but skip object-URL preview
const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500 MB hard cap per file

const currentYear = new Date().getFullYear();
const graduationYears = Array.from({ length: 111 }, (_, i) => currentYear + 10 - i);
const classes = ["A", "B", "C", "D", "E", "F"];

const graduationYear = ref<number | "">("");
const classLetter = ref<string>("");

const queue = ref<QueuedFile[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const busy = ref(false);

// Files rejected at add-time (over 500MB or unsupported type). Surfaced
// inline so the user knows why something didn't appear in the queue.
interface RejectedFile {
  id: string;
  name: string;
  size: number;
  reason: string;
}
const rejected = ref<RejectedFile[]>([]);
function clearRejected() {
  rejected.value = [];
}

// Collapsible sections — default: keep errors and pending open; collapse the
// noisy "done" list so 100 successes don't drown the rest.
const openSections = ref<Record<Status, boolean>>({
  pending: true,
  uploading: true,
  processing: true,
  error: true,
  done: false,
  duplicate: false,
});

const canSubmit = computed(
  () =>
    !busy.value &&
    queue.value.some((q) => q.status === "pending") &&
    graduationYear.value !== "" &&
    classLetter.value !== "",
);

// Single-pass tally so 100+ items don't trigger N filter() runs per tick.
const tally = computed(() => {
  const t = { total: 0, pending: 0, uploading: 0, processing: 0, done: 0, duplicate: 0, error: 0, active: 0, byteSum: 0 };
  for (const q of queue.value) {
    t.total++;
    t[q.status]++;
    if (q.status === "uploading" || q.status === "processing") t.active++;
    if (q.status === "done" || q.status === "duplicate" || q.status === "error") {
      t.byteSum += 100;
    } else if (q.status === "processing") {
      t.byteSum += 100;
    } else {
      t.byteSum += q.uploadPct;
    }
  }
  return t;
});

const overallPct = computed(() =>
  tally.value.total ? Math.round(tally.value.byteSum / tally.value.total) : 0,
);

// Group items by status for the sectioned UI. Build once per queue mutation.
const groups = computed(() => {
  const buckets: Record<Status, QueuedFile[]> = {
    pending: [],
    uploading: [],
    processing: [],
    done: [],
    duplicate: [],
    error: [],
  };
  for (const q of queue.value) buckets[q.status].push(q);
  return buckets;
});

const SECTION_ORDER: Array<{ key: Status; label: string; tone: string }> = [
  { key: "error", label: "Com erro", tone: "error" },
  { key: "uploading", label: "Enviando", tone: "active" },
  { key: "processing", label: "Processando", tone: "active" },
  { key: "pending", label: "Aguardando", tone: "neutral" },
  { key: "done", label: "Concluídas", tone: "success" },
  { key: "duplicate", label: "Já existiam", tone: "muted" },
];

function addFiles(files: FileList | File[]) {
  const arr = Array.from(files);
  for (const file of arr) {
    const kind: "image" | "video" | null = file.type.startsWith("image/")
      ? "image"
      : file.type.startsWith("video/")
        ? "video"
        : null;
    if (!kind) {
      rejected.value.push({
        id: crypto.randomUUID(),
        name: file.name,
        size: file.size,
        reason: "tipo de arquivo não suportado",
      });
      continue;
    }
    if (file.size > MAX_FILE_SIZE) {
      rejected.value.push({
        id: crypto.randomUUID(),
        name: file.name,
        size: file.size,
        reason: `arquivo maior que ${MAX_FILE_SIZE / 1024 / 1024} MB`,
      });
      continue;
    }
    // Skip preview object URLs once we're past the cap — huge file lists
    // would otherwise hold gigabytes of blob references alive.
    const preview =
      queue.value.length < MAX_PREVIEW && kind === "image"
        ? URL.createObjectURL(file)
        : "";
    queue.value.push({
      id: crypto.randomUUID(),
      file,
      preview,
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

function freePreview(item: QueuedFile) {
  if (item.preview) {
    try {
      URL.revokeObjectURL(item.preview);
    } catch {
      /* ignore */
    }
    item.preview = "";
  }
}

function removeItem(id: string) {
  const idx = queue.value.findIndex((q) => q.id === id);
  if (idx < 0) return;
  const item = queue.value[idx];
  item.abort?.abort();
  freePreview(item);
  queue.value.splice(idx, 1);
}

function clearDone() {
  const remaining: QueuedFile[] = [];
  for (const q of queue.value) {
    if (q.status === "done" || q.status === "duplicate") freePreview(q);
    else remaining.push(q);
  }
  queue.value = remaining;
}

function clearErrors() {
  const remaining: QueuedFile[] = [];
  for (const q of queue.value) {
    if (q.status === "error") freePreview(q);
    else remaining.push(q);
  }
  queue.value = remaining;
}

function retryErrors() {
  for (const q of queue.value) {
    if (q.status === "error") {
      q.status = "pending";
      q.message = undefined;
      q.uploadPct = 0;
    }
  }
  if (canSubmit.value) uploadAll();
}

function toggleSection(s: Status) {
  openSections.value[s] = !openSections.value[s];
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
    // Once the request returns, the preview blob is no longer needed.
    freePreview(item);
    if (res?.duplicate) {
      item.status = "duplicate";
      item.message = "já existe na base";
      item.facesFound = 0;
    } else {
      item.status = "done";
      item.facesFound = res?.faces?.length ?? 0;
      const faceMsg =
        item.facesFound === 0
          ? "nenhum rosto detectado"
          : `${item.facesFound} ${item.facesFound === 1 ? "rosto" : "rostos"}`;
      item.message = `aguardando aprovação · ${faceMsg}`;
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

onBeforeUnmount(() => {
  for (const q of queue.value) freePreview(q);
});
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
        <p class="muted small">JPG · PNG · WebP · HEIC · MP4 · MOV · WebM · até 500 MB</p>
      </div>
    </div>

    <!-- Rejected files (over 500MB / unsupported) -->
    <div v-if="rejected.length" class="rejected">
      <div class="rejected-head">
        <strong>{{ rejected.length }} arquivo{{ rejected.length === 1 ? "" : "s" }} ignorado{{ rejected.length === 1 ? "" : "s" }}</strong>
        <button type="button" class="link-btn" @click="clearRejected">Dispensar</button>
      </div>
      <ul>
        <li v-for="r in rejected" :key="r.id">
          <span class="filename" :title="r.name">{{ r.name }}</span>
          <span class="muted small">({{ (r.size / 1024 / 1024).toFixed(1) }} MB) · {{ r.reason }}</span>
        </li>
      </ul>
    </div>

    <!-- Sticky summary -->
    <div v-if="tally.total" class="summary">
      <div class="summary-row">
        <strong>{{ tally.total }}</strong>
        <span class="muted">arquivos · {{ overallPct }}%</span>
        <span v-if="tally.error" class="pill pill-error">{{ tally.error }} com erro</span>
        <span v-if="tally.duplicate" class="pill pill-muted">{{ tally.duplicate }} duplicada{{ tally.duplicate === 1 ? "" : "s" }}</span>
        <span v-if="tally.done" class="pill pill-success">{{ tally.done }} ok</span>
      </div>
      <div class="overall-bar">
        <div class="overall-fill" :style="{ width: overallPct + '%' }"></div>
      </div>
      <div v-if="tally.error || tally.done" class="summary-actions">
        <button v-if="tally.error" type="button" class="link-btn" @click="retryErrors">
          ↻ Tentar erros de novo
        </button>
        <button v-if="tally.error" type="button" class="link-btn" @click="clearErrors">
          Limpar erros
        </button>
        <button v-if="tally.done || tally.duplicate" type="button" class="link-btn" @click="clearDone">
          Limpar enviadas
        </button>
      </div>
    </div>

    <!-- Sectioned queue -->
    <div v-if="tally.total" class="sections">
      <template v-for="section in SECTION_ORDER" :key="section.key">
        <section v-if="groups[section.key].length" class="section">
          <button
            type="button"
            class="section-head"
            :class="['tone-' + section.tone, { collapsed: !openSections[section.key] }]"
            @click="toggleSection(section.key)"
          >
            <span class="caret" aria-hidden="true">{{ openSections[section.key] ? "▾" : "▸" }}</span>
            <span class="section-label">{{ section.label }}</span>
            <span class="section-count">{{ groups[section.key].length }}</span>
          </button>

          <ul v-if="openSections[section.key]" class="queue-list">
            <li v-for="q in groups[section.key]" :key="q.id" :class="['queue-item', q.status]">
              <div class="thumb" :class="{ 'thumb-video': q.kind === 'video' || !q.preview }">
                <img
                  v-if="q.preview && q.kind === 'image'"
                  :src="q.preview"
                  alt=""
                  loading="lazy"
                  decoding="async"
                />
                <span v-else class="thumb-icon" aria-hidden="true">
                  {{ q.kind === "video" ? "▶" : "🖼" }}
                </span>
              </div>
              <div class="info">
                <div class="row">
                  <strong class="filename" :title="q.file.name">{{ q.file.name }}</strong>
                  <button
                    v-if="q.status === 'pending' || q.status === 'uploading' || q.status === 'processing'"
                    type="button"
                    class="remove"
                    :aria-label="q.status === 'pending' ? 'remover' : 'cancelar'"
                    @click="removeItem(q.id)"
                  >✕</button>
                </div>

                <!-- One-line meta: size + inline status -->
                <span class="meta-line">
                  <span class="muted small">{{ (q.file.size / 1024 / 1024).toFixed(1) }} MB</span>
                  <span class="muted small">·</span>
                  <span class="status-text">
                    <template v-if="q.status === 'pending'">Aguardando</template>
                    <template v-else-if="q.status === 'uploading'">{{ q.uploadPct }}%</template>
                    <template v-else-if="q.status === 'processing'">Analisando rostos…</template>
                    <template v-else-if="q.status === 'done'">✓ {{ q.message }}</template>
                    <template v-else-if="q.status === 'duplicate'">⏭ {{ q.message }}</template>
                    <template v-else-if="q.status === 'error'">✗ {{ q.message }}</template>
                  </span>
                </span>

                <!-- Per-item progress bar -->
                <div
                  v-if="q.status === 'uploading' || q.status === 'processing'"
                  class="bar"
                >
                  <div
                    class="bar-fill"
                    :class="{ indeterminate: q.status === 'processing' }"
                    :style="{ width: q.status === 'processing' ? '100%' : q.uploadPct + '%' }"
                  ></div>
                </div>
              </div>
            </li>
          </ul>
        </section>
      </template>
    </div>

    <!-- Sticky action bar (mobile-friendly) -->
    <div class="actions">
      <button class="button" :disabled="!canSubmit" @click="uploadAll">
        <template v-if="busy">Enviando {{ tally.active }} de {{ tally.total }}…</template>
        <template v-else>Enviar {{ tally.pending || "" }} {{ tally.pending === 1 ? "arquivo" : "arquivos" }}</template>
      </button>
      <button
        v-if="busy"
        type="button"
        class="button secondary"
        @click="cancelAll"
      >
        Cancelar
      </button>
    </div>
  </section>
</template>

<style scoped>
.card { padding: 1rem; }

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
.form-grid em { color: var(--accent); font-style: normal; }

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

/* Rejected files list (over 500MB / unsupported) */
.rejected {
  margin-top: 0.75rem;
  padding: 0.6rem 0.85rem;
  border: 1px solid rgba(214, 58, 58, 0.3);
  border-radius: 10px;
  background: rgba(214, 58, 58, 0.06);
}
.rejected-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}
.rejected-head strong { color: var(--error); font-size: 0.88rem; }
.rejected ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.rejected li {
  display: flex;
  gap: 0.4rem;
  align-items: baseline;
  font-size: 0.82rem;
}
.rejected .filename {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}

/* Sticky summary bar */
.summary {
  position: sticky;
  top: 0;
  z-index: 5;
  margin: 1rem -1rem 0.5rem;
  padding: 0.6rem 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(6px);
}
.summary-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.4rem;
}
.summary-row strong { font-size: 1rem; }
.pill {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.1rem 0.5rem;
  border-radius: 99px;
  letter-spacing: 0.02em;
}
.pill-success { background: rgba(74, 222, 128, 0.18); color: #1f6d3f; }
.pill-error   { background: rgba(214, 58, 58, 0.15);  color: var(--error); }
.pill-muted   { background: var(--surface-strong);    color: var(--muted); }
.overall-bar {
  height: 4px;
  background: var(--surface-strong);
  border-radius: 99px;
  overflow: hidden;
}
.overall-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--marista-blue), var(--marista-blue-soft));
  transition: width 0.3s ease;
}
.summary-actions {
  display: flex;
  gap: 0.85rem;
  margin-top: 0.4rem;
  flex-wrap: wrap;
}
.link-btn {
  background: none;
  border: none;
  color: var(--marista-blue);
  cursor: pointer;
  font-size: 0.82rem;
  padding: 0;
}
.link-btn:hover { text-decoration: underline; }

/* Sectioned queue */
.sections {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.section {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--surface);
}
.section-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.55rem 0.75rem;
  background: var(--surface-strong);
  border: none;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  font-size: 0.85rem;
  color: var(--text);
  text-align: left;
}
.section-head .caret {
  width: 14px;
  display: inline-block;
  color: var(--muted);
  font-size: 0.7rem;
}
.section-head .section-label { flex: 1; }
.section-head .section-count {
  font-size: 0.72rem;
  font-weight: 700;
  background: rgba(14, 109, 194, 0.12);
  color: var(--marista-blue);
  padding: 0.1rem 0.5rem;
  border-radius: 99px;
}
.section-head.tone-error    .section-count { background: rgba(214, 58, 58, 0.15);  color: var(--error); }
.section-head.tone-success  .section-count { background: rgba(74, 222, 128, 0.18); color: #1f6d3f; }
.section-head.tone-active   .section-count { background: rgba(247, 201, 72, 0.25); color: #8a6913; }
.section-head.tone-muted    .section-count { background: var(--surface);           color: var(--muted); }

.queue-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  max-height: 50vh;
  overflow-y: auto;
}
.queue-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0.6rem;
  border-top: 1px solid var(--border);
}
.queue-item:first-child { border-top: none; }
.thumb {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--surface-strong);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb-icon { font-size: 1.1rem; color: var(--muted); }
.thumb-video { background: linear-gradient(135deg, rgba(12,44,79,0.08), rgba(247,201,72,0.08)); }

.info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 0;
}
.info .row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.4rem;
}
.filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.85rem;
  min-width: 0;
}
.meta-line {
  display: flex;
  gap: 0.35rem;
  align-items: baseline;
  flex-wrap: wrap;
}
.bar {
  height: 3px;
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
.status-text { font-size: 0.78rem; color: var(--muted); }
.queue-item.done .status-text { color: #1f6d3f; }
.queue-item.duplicate { opacity: 0.7; }
.queue-item.error .status-text { color: var(--error); }
.remove {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.95rem;
  padding: 2px 6px;
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
  .summary { margin: 1rem -1.5rem 0.5rem; padding: 0.6rem 1.5rem; }
}
</style>
