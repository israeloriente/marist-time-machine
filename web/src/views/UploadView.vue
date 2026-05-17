<script setup lang="ts">
import { computed, ref } from "vue";
import { uploadPhoto } from "@/services/api";

interface QueuedFile {
  id: string;
  file: File;
  preview: string;
  kind: "image" | "video";
  status: "pending" | "uploading" | "done" | "error";
  message?: string;
  facesFound?: number;
}

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

const doneCount = computed(() => queue.value.filter((q) => q.status === "done").length);
const errorCount = computed(() => queue.value.filter((q) => q.status === "error").length);

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
  if (idx >= 0) {
    URL.revokeObjectURL(queue.value[idx].preview);
    queue.value.splice(idx, 1);
  }
}

function clearDone() {
  queue.value = queue.value.filter((q) => q.status !== "done");
}

async function uploadAll() {
  busy.value = true;
  const metadata = {
    graduation_year: graduationYear.value,
    class: classLetter.value,
  };

  for (const item of queue.value) {
    if (item.status !== "pending") continue;
    item.status = "uploading";
    try {
      const res = await uploadPhoto(item.file, metadata);
      item.status = "done";
      item.facesFound = res?.faces?.length ?? 0;
      item.message =
        item.facesFound === 0
          ? "nenhum rosto detectado"
          : `${item.facesFound} ${item.facesFound === 1 ? "rosto" : "rostos"} detectados`;
    } catch (e: any) {
      item.status = "error";
      item.message = e.response?.data?.detail ?? e.message ?? String(e);
    }
  }
  busy.value = false;
}
</script>

<template>
  <section class="card">
    <h2>Adicionar ao acervo</h2>
    <p class="muted">
      Envie fotos ou vídeos. Para vídeos, um frame representativo é processado
      pra reconhecimento facial.
    </p>

    <!-- Metadata form -->
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
      <p>
        <strong>Arraste fotos ou vídeos aqui</strong> ou clique para selecionar.<br />
        <span class="muted">Aceita JPG, PNG, WebP, HEIC, MP4, MOV, WebM.</span>
      </p>
    </div>

    <!-- Queue -->
    <div v-if="queue.length" style="margin-top: 1.25rem">
      <div
        style="
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.5rem;
          margin-bottom: 0.75rem;
        "
      >
        <p class="muted" style="margin: 0">
          {{ queue.length }} {{ queue.length === 1 ? "arquivo" : "arquivos" }} na fila
          <span v-if="doneCount">— ✓ {{ doneCount }} enviados</span>
          <span v-if="errorCount" class="error"> — ✗ {{ errorCount }} com erro</span>
        </p>
        <button v-if="doneCount" class="button secondary" type="button" @click="clearDone">
          Limpar enviados
        </button>
      </div>

      <ul class="queue-list">
        <li v-for="q in queue" :key="q.id" :class="['queue-item', q.status]">
          <div class="thumb">
            <img v-if="q.kind === 'image'" :src="q.preview" alt="" />
            <video v-else :src="q.preview" muted />
            <span class="badge">{{ q.kind === "video" ? "vídeo" : "foto" }}</span>
          </div>
          <div class="info">
            <strong>{{ q.file.name }}</strong>
            <span class="muted">{{ (q.file.size / 1024 / 1024).toFixed(1) }} MB</span>
            <span v-if="q.status === 'uploading'">Enviando…</span>
            <span v-if="q.status === 'done'">✓ {{ q.message }}</span>
            <span v-if="q.status === 'error'" class="error">✗ {{ q.message }}</span>
          </div>
          <button
            v-if="q.status === 'pending'"
            type="button"
            class="remove"
            @click="removeItem(q.id)"
            aria-label="remover"
          >
            ✕
          </button>
        </li>
      </ul>
    </div>

    <div style="display: flex; gap: 0.75rem; margin-top: 1.25rem; flex-wrap: wrap">
      <button class="button" :disabled="!canSubmit" @click="uploadAll">
        {{ busy ? "Enviando..." : "Enviar todos" }}
      </button>
      <button
        v-if="!busy && queue.length"
        class="button secondary"
        type="button"
        @click="queue = []"
      >
        Cancelar tudo
      </button>
    </div>
  </section>
</template>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  margin: 1rem 0 1.25rem;
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
  border: 2px dashed #2d4a82;
  border-radius: 12px;
  padding: 2rem 1rem;
  text-align: center;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s;
  background: rgba(45, 74, 130, 0.08);
}
.dropzone:hover,
.dropzone.over {
  border-color: var(--accent);
  background: rgba(255, 211, 78, 0.08);
}
.dropzone p {
  margin: 0;
  color: var(--text);
}

.queue-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.queue-item {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.6rem;
  border-radius: 10px;
  background: rgba(11, 31, 58, 0.4);
  border: 1px solid #1d3258;
}
.thumb {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 6px;
  overflow: hidden;
  background: #1a2c4e;
  flex-shrink: 0;
}
.thumb img,
.thumb video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb .badge {
  position: absolute;
  bottom: 2px;
  right: 2px;
  background: rgba(0, 0, 0, 0.7);
  color: var(--accent);
  font-size: 0.65rem;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
}
.queue-item .info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 0;
}
.queue-item .info strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.queue-item.done {
  border-color: rgba(0, 200, 100, 0.4);
}
.queue-item.error {
  border-color: rgba(255, 107, 107, 0.4);
}
.remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: var(--muted);
}
</style>
