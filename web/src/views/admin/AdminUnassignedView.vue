<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import CenteredNotice from "@/components/CenteredNotice.vue";
import FaceThumb from "@/components/FaceThumb.vue";
import PersonPickerDialog from "@/components/PersonPickerDialog.vue";
import { facesApi, type Face, type Person } from "@/services/api";
import { useNotifyStore } from "@/stores/notify";

type Tab = "active" | "rejected";

const notify = useNotifyStore();

const tab = ref<Tab>("active");
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
    const batch = await facesApi.unassigned(
      50,
      offset.value,
      0.5,
      tab.value === "rejected",
    );
    unassigned.value.push(...batch);
    offset.value += batch.length;
    hasMore.value = batch.length === 50;
  } finally {
    loading.value = false;
  }
}

async function promoteToPerson(face: Face) {
  const name = await notify.prompt({
    title: "Promover a pessoa",
    message: "Dê um nome (opcional) ou deixe em branco pra criar como anônima.",
    placeholder: "Nome (opcional)",
    confirmLabel: "Criar pessoa",
  });
  if (name === null) return;
  try {
    await facesApi.promote(face.id, name || undefined);
    unassigned.value = unassigned.value.filter((f) => f.id !== face.id);
  } catch (e) {
    notify.error("Erro ao promover rosto", e);
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
  } catch (e) {
    notify.error("Erro ao atribuir rosto", e);
  }
}

async function rejectFace(face: Face) {
  const ok = await notify.confirm({
    title: "Rejeitar este rosto?",
    message:
      "Marcar como não-pessoa (objeto detectado por engano, captura ruim, etc). Some das buscas e do /contribute. Pode ser reativado pela aba 'Rejeitados'.",
    confirmLabel: "Rejeitar",
    variant: "danger",
  });
  if (!ok) return;
  try {
    await facesApi.reject(face.id, true);
    unassigned.value = unassigned.value.filter((f) => f.id !== face.id);
    notify.success("Rosto rejeitado.");
  } catch (e) {
    notify.error("Erro ao rejeitar rosto", e);
  }
}

async function reactivateFace(face: Face) {
  try {
    await facesApi.reject(face.id, false);
    unassigned.value = unassigned.value.filter((f) => f.id !== face.id);
    notify.success("Rosto reativado.");
  } catch (e) {
    notify.error("Erro ao reativar rosto", e);
  }
}

watch(tab, () => load(true));
onMounted(() => load(true));
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Rostos não atribuídos</h1>
      <p class="muted">Rostos que ainda não foram agrupados em uma pessoa.</p>
    </div>
  </header>

  <div class="tabs">
    <button :class="{ active: tab === 'active' }" @click="tab = 'active'">
      Ativos
    </button>
    <button :class="{ active: tab === 'rejected' }" @click="tab = 'rejected'">
      Rejeitados
    </button>
  </div>

  <CenteredNotice v-if="loading && !unassigned.length" variant="loading">
    Carregando…
  </CenteredNotice>
  <CenteredNotice v-else-if="!unassigned.length" variant="empty">
    <template v-if="tab === 'active'">
      🎉 Todos os rostos detectados já estão atribuídos a uma pessoa.
    </template>
    <template v-else>Nenhum rosto rejeitado.</template>
  </CenteredNotice>
  <div v-else class="faces-grid">
    <div v-for="f in unassigned" :key="f.id" class="face-card">
      <FaceThumb :src="f.signed_url" :bbox="f.bbox" :size="96" :padding="0.3" />
      <span class="muted small">{{ (f.detection_score * 100).toFixed(0) }}%</span>
      <div class="actions">
        <template v-if="tab === 'active'">
          <button class="button small" @click="promoteToPerson(f)" title="Nova pessoa">+ Nova</button>
          <button class="button small secondary" @click="openAssignPicker(f)" title="Atribuir">→ Existente</button>
          <button class="button small danger" @click="rejectFace(f)" title="Rejeitar">✕ Rejeitar</button>
        </template>
        <template v-else>
          <button class="button small" @click="reactivateFace(f)" title="Reativar">↺ Reativar</button>
        </template>
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

.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
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
}
.tabs button.active {
  color: var(--marista-navy);
  border-bottom-color: var(--marista-yellow);
  font-weight: 700;
}

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
.button.small.danger {
  background: var(--error);
  color: white;
}
.button.small.danger:hover:not(:disabled) { background: #b32f2f; }
.small { font-size: 0.75rem; }
</style>
