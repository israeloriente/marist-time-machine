<script setup lang="ts">
import { computed, ref } from "vue";
import { uploadPhoto } from "@/services/api";

interface QueuedFile {
  id: string;
  file: File;
  preview: string;
  status: "pending" | "uploading" | "done" | "error";
  message?: string;
  facesFound?: number;
}

const yearPhoto = ref<number | null>(null);
const eventLabel = ref("");
const yearGraduation = ref<number | null>(null);

const queue = ref<QueuedFile[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const busy = ref(false);

const currentYear = new Date().getFullYear();

const canSubmit = computed(
  () => !busy.value && queue.value.some((q) => q.status === "pending") && yearPhoto.value,
);

const doneCount = computed(() => queue.value.filter((q) => q.status === "done").length);
const errorCount = computed(() => queue.value.filter((q) => q.status === "error").length);

function addFiles(files: FileList | File[]) {
  for (const file of Array.from(files)) {
    if (!file.type.startsWith("image/")) continue;
    queue.value.push({
      id: crypto.randomUUID(),
      file,
      preview: URL.createObjectURL(file),
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
    photo_year: yearPhoto.value,
    event: eventLabel.value || null,
    graduation_year: yearGraduation.value,
  };

  for (const item of queue.value) {
    if (item.status !== "pending") continue;
    item.status = "uploading";
    try {
      const res = await uploadPhoto(item.file, metadata);
      item.status = "done";
      item.facesFound = res?.faces?.length ?? 0;
      item.message = `${item.facesFound} ${item.facesFound === 1 ? "rosto" : "rostos"} detectados`;
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
    <h2>Adicionar fotos ao acervo</h2>
    <p class="muted">
      Arraste fotos para enviar à Máquina do Tempo. Cada rosto detectado vira
      parte da busca por similaridade.
    </p>

    <!-- Metadata form -->
    <div class="form-grid">
      <label>
        <span>Ano da foto <em>*</em></span>
        <input
          v-model.number="yearPhoto"
          class="input"
          type="number"
          :min="1900"
          :max="currentYear"
          placeholder="ex: 2010"
          required
        />
      </label>
      <label>
        <span>Evento ou turma</span>
        <input
          v-model="eventLabel"
          class="input"
          type="text"
          placeholder="ex: Formatura, 6º ano, Festa Junina"
        />
      </label>
      <label>
        <span>Ano de formatura</span>
        <input
          v-model.number="yearGraduation"
          class="input"
          type="number"
          :min="1900"
          :max="currentYear + 10"
          placeholder="ex: 2015"
        />
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
        accept="image/*"
        multiple
        hidden
        @change="onFilesPicked"
      />
      <p>
        <strong>Arraste fotos aqui</strong> ou clique para selecionar.<br />
        <span class="muted">Aceita JPG, PNG, WebP, HEIC.</span>
      </p>
    </div>

    <!-- Queue -->
    <div v-if="queue.length" style="margin-top: 1.25rem">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.75rem">
        <p class="muted" style="margin: 0">
          {{ queue.length }} {{ queue.length === 1 ? "foto" : "fotos" }} na fila
          <span v-if="doneCount">— ✓ {{ doneCount }} enviadas</span>
          <span v-if="errorCount" class="error"> — ✗ {{ errorCount }} com erro</span>
        </p>
        <button v-if="doneCount" class="button secondary" type="button" @click="clearDone">
          Limpar enviadas
        </button>
      </div>

      <ul class="queue-list">
        <li v-for="q in queue" :key="q.id" :class="['queue-item', q.status]">
          <img :src="q.preview" alt="" />
          <div class="info">
            <strong>{{ q.file.name }}</strong>
            <span class="muted">{{ (q.file.size / 1024).toFixed(0) }} KB</span>
            <span v-if="q.status === 'uploading'">Enviando…</span>
            <span v-if="q.status === 'done'">✓ {{ q.message }}</span>
            <span v-if="q.status === 'error'" class="error">✗ {{ q.message }}</span>
          </div>
          <button
            v-if="q.status === 'pending'"
            type="button"
            class="link muted"
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
        {{ busy ? "Enviando..." : "Enviar todas" }}
      </button>
      <button v-if="!busy && queue.length" class="button secondary" type="button" @click="queue = []">
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
  transition: background 0.2s, border-color 0.2s;
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
.queue-item img {
  width: 56px;
  height: 56px;
  border-radius: 6px;
  object-fit: cover;
  background: #1a2c4e;
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
.queue-item button {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
}
</style>
