<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { searchByFace, type SearchResponse } from "@/services/api";
import { useResultsStore } from "@/stores/results";

const router = useRouter();
const results = useResultsStore();

const videoRef = ref<HTMLVideoElement | null>(null);
const stream = ref<MediaStream | null>(null);
const error = ref<string | null>(null);
const busy = ref(false);
const preview = ref<string | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

async function startCamera() {
  error.value = null;
  try {
    stream.value = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: 1280, height: 720 },
      audio: false,
    });
    if (videoRef.value) {
      videoRef.value.srcObject = stream.value;
      await videoRef.value.play();
    }
  } catch (e: any) {
    error.value = `Não consegui acessar a câmera: ${e.message ?? e}`;
  }
}

function stopCamera() {
  stream.value?.getTracks().forEach((t) => t.stop());
  stream.value = null;
}

async function snapshot(): Promise<Blob | null> {
  if (!videoRef.value) return null;
  const v = videoRef.value;
  const canvas = document.createElement("canvas");
  canvas.width = v.videoWidth;
  canvas.height = v.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(v, 0, 0);
  return await new Promise((res) => canvas.toBlob((b) => res(b), "image/jpeg", 0.92));
}

async function captureAndSearch() {
  busy.value = true;
  error.value = null;
  try {
    const blob = await snapshot();
    if (!blob) throw new Error("falha ao capturar imagem");
    preview.value = URL.createObjectURL(blob);
    const data: SearchResponse = await searchByFace(blob);
    results.set(data);
    stopCamera();
    router.push({ name: "results" });
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    busy.value = false;
  }
}

async function uploadFile(evt: Event) {
  const target = evt.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  busy.value = true;
  error.value = null;
  try {
    preview.value = URL.createObjectURL(file);
    const data = await searchByFace(file);
    results.set(data);
    router.push({ name: "results" });
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    busy.value = false;
  }
}

onMounted(startCamera);
onBeforeUnmount(stopCamera);
</script>

<template>
  <section class="card">
    <h2>Mostre seu rosto</h2>
    <p class="muted">Centralize seu rosto na câmera e toque em buscar.</p>

    <div v-if="error" class="error" style="margin-top: 0.75rem">{{ error }}</div>

    <div style="margin-top: 1rem; aspect-ratio: 4/3; background: var(--marista-navy); border-radius: 12px; overflow: hidden">
      <video ref="videoRef" playsinline muted style="width: 100%; height: 100%; object-fit: cover" />
    </div>

    <div style="display: flex; gap: 0.75rem; margin-top: 1rem; flex-wrap: wrap">
      <button class="button" :disabled="busy || !stream" @click="captureAndSearch">
        {{ busy ? "Buscando..." : "Buscar" }}
      </button>
      <button class="button secondary" type="button" @click="fileInput?.click()">
        Enviar foto
      </button>
      <input ref="fileInput" type="file" accept="image/*" hidden @change="uploadFile" />
    </div>
  </section>
</template>
