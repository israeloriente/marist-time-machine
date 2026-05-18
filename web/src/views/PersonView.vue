<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import FaceThumb from "@/components/FaceThumb.vue";
import PersonPickerDialog from "@/components/PersonPickerDialog.vue";
import {
  facesApi,
  peopleApi,
  suggestionsApi,
  type Face,
  type Person,
  type PersonPhoto,
  type SuggestionGroup,
} from "@/services/api";

const route = useRoute();
const router = useRouter();
const personId = route.params.id as string;

const person = ref<Person | null>(null);
const faces = ref<Face[]>([]);
const photos = ref<PersonPhoto[]>([]);
const suggestions = ref<SuggestionGroup[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const renameValue = ref("");
const savingName = ref(false);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const list = await peopleApi.list();
    person.value = list.find((p) => p.id === personId) ?? null;
    if (!person.value) {
      error.value = "Pessoa não encontrada.";
      return;
    }
    renameValue.value = person.value.display_name ?? "";
    [faces.value, photos.value, suggestions.value] = await Promise.all([
      peopleApi.faces(personId),
      peopleApi.photos(personId),
      suggestionsApi.byPerson(personId).catch(() => []),
    ]);
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    loading.value = false;
  }
}

async function saveName() {
  if (!person.value) return;
  savingName.value = true;
  try {
    const updated = await peopleApi.rename(personId, renameValue.value.trim() || null);
    person.value.display_name = updated.display_name;
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  } finally {
    savingName.value = false;
  }
}

async function detachFace(face: Face) {
  if (!confirm("Remover esse rosto desta pessoa? Ele voltará para 'não atribuídos'.")) return;
  try {
    await facesApi.reassign(face.id, null);
    faces.value = faces.value.filter((f) => f.id !== face.id);
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

const showMergePicker = ref(false);

function openMergePicker() {
  showMergePicker.value = true;
}

async function onMergePick(target: Person) {
  const targetName = target.display_name || `Pessoa ${target.id.slice(0, 8)}`;
  if (!confirm(`Mesclar TODOS os rostos desta pessoa em "${targetName}"?\n\nEsta pessoa será apagada.`)) return;
  try {
    await peopleApi.merge(personId, target.id);
    showMergePicker.value = false;
    router.push({ name: "person", params: { id: target.id } });
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

async function approveSuggestion(g: SuggestionGroup) {
  // Use the first (newest) suggestion id; admin may edit the name.
  const final = prompt("Aprovar com qual nome?", g.suggested_name)?.trim();
  if (final === undefined) return;
  try {
    await suggestionsApi.approve(g.suggestion_ids[0], final || undefined);
    // Refresh
    await load();
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

async function rejectSuggestion(g: SuggestionGroup) {
  if (!confirm(`Rejeitar "${g.suggested_name}" (${g.vote_count} ${g.vote_count === 1 ? "voto" : "votos"})?`)) return;
  try {
    await suggestionsApi.reject(g.suggestion_ids[0]);
    suggestions.value = suggestions.value.filter((s) => s !== g);
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

async function hidePerson() {
  if (!confirm("Esconder esta pessoa? Ela não aparecerá na lista admin nem em buscas.")) return;
  try {
    await peopleApi.hide(personId, true);
    router.push({ name: "admin" });
  } catch (e: any) {
    alert("Erro: " + (e.response?.data?.detail ?? e.message));
  }
}

onMounted(load);
</script>

<template>
  <section class="card">
    <div class="back-row">
      <RouterLink to="/admin/pessoas" class="muted">← Voltar pra Pessoas</RouterLink>
    </div>

    <p v-if="loading" class="muted">Carregando…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="person">
      <div class="header">
        <FaceThumb
          v-if="faces[0]"
          :src="faces[0].signed_url"
          :bbox="faces[0].bbox"
          :size="96"
          :padding="0.3"
        />
        <div class="title">
          <input
            v-model="renameValue"
            class="input name-input"
            placeholder="Nome desta pessoa"
            @blur="saveName"
            @keydown.enter="saveName"
          />
          <span class="muted small">
            {{ faces.length }} {{ faces.length === 1 ? "rosto" : "rostos" }} ·
            {{ photos.length }} {{ photos.length === 1 ? "foto" : "fotos" }}
            <span v-if="savingName"> · salvando…</span>
          </span>
        </div>
      </div>

      <div class="ops">
        <button class="button secondary" @click="openMergePicker">Mesclar com…</button>
        <button class="button secondary" @click="hidePerson">Esconder</button>
      </div>

      <PersonPickerDialog
        :open="showMergePicker"
        title="Mesclar em qual pessoa?"
        confirm-label="Mesclar"
        :exclude-id="personId"
        @close="showMergePicker = false"
        @pick="onMergePick"
      />

      <!-- Pending name suggestions -->
      <div v-if="suggestions.length" class="suggestions">
        <h3>Sugestões pendentes</h3>
        <ul class="sugg-list">
          <li v-for="g in suggestions" :key="g.suggestion_ids[0]" class="sugg-item">
            <div class="sugg-info">
              <strong>{{ g.suggested_name }}</strong>
              <span class="muted small">
                {{ g.vote_count }} {{ g.vote_count === 1 ? "voto" : "votos" }}
              </span>
            </div>
            <div class="sugg-ops">
              <button class="button small" @click="approveSuggestion(g)">Aprovar</button>
              <button class="button small secondary" @click="rejectSuggestion(g)">Rejeitar</button>
            </div>
          </li>
        </ul>
      </div>

      <h3 style="margin-top: 1.5rem">Rostos atribuídos</h3>
      <p v-if="!faces.length" class="muted small">Nenhum rosto.</p>
      <div v-else class="faces-grid">
        <div v-for="f in faces" :key="f.id" class="face-cell">
          <FaceThumb :src="f.signed_url" :bbox="f.bbox" :size="72" :padding="0.3" />
          <button
            class="detach"
            title="Remover desta pessoa"
            @click="detachFace(f)"
          >✕</button>
        </div>
      </div>

      <h3 style="margin-top: 1.5rem">Fotos onde aparece</h3>
      <p v-if="!photos.length" class="muted small">Nenhuma foto.</p>
      <div v-else class="photos-grid">
        <a
          v-for="p in photos"
          :key="p.id"
          :href="p.signed_url"
          target="_blank"
          rel="noopener"
        >
          <img :src="p.signed_url" loading="lazy" :alt="p.id" />
        </a>
      </div>
    </template>
  </section>
</template>

<style scoped>
.back-row {
  margin-bottom: 0.75rem;
}
.back-row a {
  text-decoration: none;
}

.header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
}
.title { display: flex; flex-direction: column; gap: 0.25rem; flex: 1; min-width: 0; }
.name-input { font-size: 1.1rem; font-weight: 700; }

.ops {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
}

.faces-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 0.5rem;
}
.face-cell { position: relative; }
.detach {
  position: absolute;
  top: -6px; right: -6px;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--error);
  color: white;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  display: flex; align-items: center; justify-content: center;
}

.photos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 0.5rem;
}
.photos-grid img {
  width: 100%; aspect-ratio: 1/1; object-fit: cover;
  border-radius: 8px; background: var(--surface-strong);
}
.small { font-size: 0.85rem; }

.suggestions {
  margin-top: 1.25rem;
  padding: 0.75rem;
  background: rgba(247, 201, 72, 0.10);
  border: 1px solid rgba(247, 201, 72, 0.35);
  border-radius: 10px;
}
.suggestions h3 { margin: 0 0 0.5rem; font-size: 1rem; }
.sugg-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.4rem; }
.sugg-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--surface-strong);
  border-radius: 8px;
  flex-wrap: wrap;
}
.sugg-info { display: flex; flex-direction: column; min-width: 0; }
.sugg-info strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sugg-ops { display: flex; gap: 0.35rem; }
.button.small {
  min-height: 32px;
  padding: 0.3rem 0.7rem;
  font-size: 0.85rem;
}
</style>
