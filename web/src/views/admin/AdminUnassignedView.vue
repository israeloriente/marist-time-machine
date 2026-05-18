<script setup lang="ts">
import { onMounted, ref } from "vue";
import FaceThumb from "@/components/FaceThumb.vue";
import PersonPickerDialog from "@/components/PersonPickerDialog.vue";
import { facesApi, type Face, type Person } from "@/services/api";

const unassigned = ref<Face[]>([]);
const loading = ref(false);
const offset = ref(0);
const hasMore = ref(true);
const showAssignPicker = ref(false);
const faceBeingAssigned = ref<Face | null>(null);

async function load(reset = false) {
  if (reset) {
    unassigned.value = [];
    offset.value = 0;
    hasMore.value = true;
  }
  if (!hasMore.value) return;
  loading.value = true;
  try {
    const batch = await facesApi.unassigned(50, offset.value, 0.5);
    unassigned.value.push(...batch);
    offset.value += batch.length;
    hasMore.value = batch.length === 50;
  } finally {
    loading.value = false;
  }
}

async function promoteToPerson(face: Face) {
  const name = prompt("Nome da nova pessoa (opcional):") ?? "";
  try {
    await facesApi.promote(face.id, name || undefined);
    unassigned.value = unassigned.value.filter((f) => f.id !== face.id);
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

function openAssignPicker(face: Face) {
  faceBeingAssigned.value = face;
  showAssignPicker.value = true;
}

async function onAssignPick(person: Person) {
  const face = faceBeingAssigned.value;
  if (!face) return;
  try {
    await facesApi.reassign(face.id, person.id);
    unassigned.value = unassigned.value.filter((f) => f.id !== face.id);
    showAssignPicker.value = false;
    faceBeingAssigned.value = null;
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

onMounted(() => load(true));
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Rostos não atribuídos</h1>
      <p class="muted">Rostos que ainda não foram agrupados em uma pessoa.</p>
    </div>
  </header>

  <p v-if="loading && !unassigned.length" class="muted">Carregando…</p>
  <p v-else-if="!unassigned.length" class="muted">
    🎉 Todos os rostos detectados já estão atribuídos a uma pessoa.
  </p>
  <div v-else class="faces-grid">
    <div v-for="f in unassigned" :key="f.id" class="face-card">
      <FaceThumb :src="f.signed_url" :bbox="f.bbox" :size="96" :padding="0.3" />
      <span class="muted small">{{ (f.detection_score * 100).toFixed(0) }}%</span>
      <div class="actions">
        <button class="button small" @click="promoteToPerson(f)" title="Nova pessoa">+ Nova</button>
        <button class="button small secondary" @click="openAssignPicker(f)" title="Atribuir">→ Existente</button>
      </div>
    </div>
  </div>
  <div v-if="hasMore && unassigned.length" style="text-align: center; margin-top: 1.25rem">
    <button class="button secondary" :disabled="loading" @click="load(false)">
      {{ loading ? "Carregando…" : "Carregar mais" }}
    </button>
  </div>

  <PersonPickerDialog
    :open="showAssignPicker"
    title="Atribuir a qual pessoa?"
    confirm-label="Atribuir"
    @close="showAssignPicker = false"
    @pick="onAssignPick"
  />
</template>

<style scoped>
.page-header { margin-bottom: 1.25rem; }
.page-header h1 { margin: 0; }
.page-header p { margin: 0.2rem 0 0; }

.faces-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}
.face-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.45rem;
  padding: 0.75rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.actions { display: flex; gap: 0.25rem; flex-wrap: wrap; justify-content: center; }
.button.small {
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
}
.small { font-size: 0.75rem; }
</style>
