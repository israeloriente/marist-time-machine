<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import CenteredNotice from "@/components/CenteredNotice.vue";
import FaceThumb from "@/components/FaceThumb.vue";
import MediaPreview from "@/components/MediaPreview.vue";
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
import { useNotifyStore } from "@/stores/notify";

const notify = useNotifyStore();

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

const yearValue = ref<number | "">("");
const classValue = ref<string>("");
const savingGrad = ref(false);

const currentYear = new Date().getFullYear();
const graduationYears = Array.from({ length: 111 }, (_, i) => currentYear + 10 - i);
const classes = ["A", "B", "C", "D", "E", "F"];

async function load() {
  loading.value = true;
  error.value = null;
  try {
    // Use the dedicated endpoint so rejected people are still loadable
    // (admin needs to be able to view a rejected person to reactivate).
    person.value = await peopleApi.get(personId);
    renameValue.value = person.value.display_name ?? "";
    yearValue.value = person.value.graduation_year ?? "";
    classValue.value = person.value.class_letter ?? "";
    [faces.value, photos.value, suggestions.value] = await Promise.all([
      peopleApi.faces(personId),
      peopleApi.photos(personId),
      suggestionsApi.byPerson(personId).catch(() => []),
    ]);
  } catch (e: any) {
    if (e.response?.status === 404) {
      error.value = "Pessoa não encontrada.";
    } else {
      error.value = e.response?.data?.detail ?? e.message ?? String(e);
    }
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
  } catch (e) {
    notify.error("Erro ao salvar nome", e);
  } finally {
    savingName.value = false;
  }
}

async function saveGraduation() {
  if (!person.value) return;
  savingGrad.value = true;
  try {
    const updated = await peopleApi.updateGraduation(
      personId,
      yearValue.value === "" ? null : (yearValue.value as number),
      classValue.value || null,
    );
    person.value.graduation_year = updated.graduation_year;
    person.value.class_letter = updated.class_letter;
  } catch (e) {
    notify.error("Erro ao salvar formatura", e);
  } finally {
    savingGrad.value = false;
  }
}

async function detachFace(face: Face) {
  const ok = await notify.confirm({
    title: "Remover rosto desta pessoa?",
    message: "Ele voltará para 'não atribuídos'.",
    confirmLabel: "Remover",
    variant: "default",
  });
  if (!ok) return;
  try {
    await facesApi.reassign(face.id, null);
    faces.value = faces.value.filter((f) => f.id !== face.id);
  } catch (e) {
    notify.error("Erro ao remover rosto", e);
  }
}

const showMergePicker = ref(false);

function openMergePicker() {
  showMergePicker.value = true;
}

async function onMergePick(target: Person) {
  const targetName = target.display_name || `Pessoa ${target.id.slice(0, 8)}`;
  const ok = await notify.confirm({
    title: "Mesclar pessoas?",
    message: `Todos os rostos desta pessoa vão pra "${targetName}". Esta pessoa será apagada.`,
    confirmLabel: "Mesclar",
    variant: "danger",
  });
  if (!ok) return;
  try {
    await peopleApi.merge(personId, target.id);
    showMergePicker.value = false;
    router.push({ name: "person", params: { id: target.id } });
  } catch (e) {
    notify.error("Erro ao mesclar", e);
  }
}

async function approveSuggestion(g: SuggestionGroup) {
  const final = await notify.prompt({
    title: "Aprovar sugestão",
    message: "Aprovar com qual nome?",
    defaultValue: g.suggested_name,
    placeholder: "Nome completo",
    confirmLabel: "Aprovar",
    required: true,
  });
  if (final === null) return;
  try {
    await suggestionsApi.approve(g.suggestion_ids[0], {
      final_name: final || undefined,
      final_graduation_year: g.suggested_graduation_year ?? null,
      final_class_letter: g.suggested_class_letter ?? null,
    });
    await load();
  } catch (e) {
    notify.error("Erro ao aprovar sugestão", e);
  }
}

async function rejectSuggestion(g: SuggestionGroup) {
  const ok = await notify.confirm({
    title: "Rejeitar sugestão?",
    message: `"${g.suggested_name}" (${g.vote_count} ${g.vote_count === 1 ? "voto" : "votos"})`,
    confirmLabel: "Rejeitar",
  });
  if (!ok) return;
  try {
    await suggestionsApi.reject(g.suggestion_ids[0]);
    suggestions.value = suggestions.value.filter((s) => s !== g);
  } catch (e) {
    notify.error("Erro ao rejeitar sugestão", e);
  }
}

async function rejectPerson() {
  const ok = await notify.confirm({
    title: "Rejeitar esta pessoa?",
    message:
      "Ela some das buscas e do /contribute, mas pode ser reativada depois pela aba 'Rejeitadas'.",
    confirmLabel: "Rejeitar",
    variant: "danger",
  });
  if (!ok) return;
  try {
    const updated = await peopleApi.setStatus(personId, "rejected");
    if (person.value) person.value.status = updated.status;
  } catch (e) {
    notify.error("Erro ao rejeitar pessoa", e);
  }
}

async function reactivatePerson() {
  try {
    const updated = await peopleApi.setStatus(personId, "active");
    if (person.value) person.value.status = updated.status;
    notify.success("Pessoa reativada");
  } catch (e) {
    notify.error("Erro ao reativar pessoa", e);
  }
}

onMounted(load);
</script>

<template>
  <section class="card">
    <div class="back-row">
      <RouterLink to="/admin/pessoas" class="muted">← Voltar pra Pessoas</RouterLink>
    </div>

    <CenteredNotice v-if="loading" variant="loading">Carregando…</CenteredNotice>
    <CenteredNotice v-else-if="error" variant="error">{{ error }}</CenteredNotice>
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

      <section class="grad-section">
        <h4>Formatura</h4>
        <div class="grad-row">
          <label>
            <span>Ano</span>
            <select v-model.number="yearValue" class="input" @change="saveGraduation">
              <option value="">—</option>
              <option v-for="y in graduationYears" :key="y" :value="y">{{ y }}</option>
            </select>
          </label>
          <label>
            <span>Turma</span>
            <select v-model="classValue" class="input" @change="saveGraduation">
              <option value="">—</option>
              <option v-for="c in classes" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
          <span v-if="savingGrad" class="muted small">salvando…</span>
        </div>
        <p v-if="!person?.graduation_year && person?.graduation_years?.length" class="muted small fallback-hint">
          Derivado das fotos:
          <span v-for="y in person.graduation_years" :key="y" class="tag tag-year">{{ y }}</span>
          <span v-for="c in person.classes ?? []" :key="c" class="tag tag-class">{{ c }}</span>
        </p>
      </section>

      <div v-if="person?.status === 'rejected'" class="rejected-banner">
        <strong>Pessoa rejeitada.</strong>
        Não aparece em buscas nem no /contribute.
        <button class="link-btn" @click="reactivatePerson">↺ Reativar</button>
      </div>

      <div class="ops">
        <button class="button secondary" @click="openMergePicker">Mesclar com…</button>
        <button
          v-if="person?.status !== 'rejected'"
          class="button secondary"
          @click="rejectPerson"
        >Rejeitar</button>
        <button
          v-else
          class="button"
          @click="reactivatePerson"
        >Reativar</button>
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
          class="photo-tile"
        >
          <MediaPreview
            :src="p.signed_url"
            :thumb-src="p.thumb_signed_url"
            :media-type="p.media_type"
            :alt="p.id"
          />
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

.rejected-banner {
  margin-top: 0.75rem;
  padding: 0.65rem 0.85rem;
  border: 1px solid rgba(214, 58, 58, 0.4);
  border-radius: 8px;
  background: rgba(214, 58, 58, 0.08);
  color: var(--error);
  font-size: 0.88rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.rejected-banner strong { font-weight: 700; }
.rejected-banner .link-btn {
  background: none;
  border: none;
  color: var(--marista-blue);
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  margin-left: auto;
  padding: 0;
}
.rejected-banner .link-btn:hover { text-decoration: underline; }

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
.photo-tile {
  display: block;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-strong);
}
.small { font-size: 0.85rem; }

.grad-section {
  margin-top: 1.25rem;
  padding: 0.85rem;
  background: var(--surface-strong);
  border-radius: 10px;
}
.grad-section h4 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.grad-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 0.5rem;
  align-items: end;
}
.grad-row label {
  display: flex; flex-direction: column; gap: 0.2rem;
  font-size: 0.8rem; color: var(--muted);
}
.fallback-hint {
  margin: 0.5rem 0 0;
  display: flex; gap: 0.3rem; align-items: center; flex-wrap: wrap;
}
.tag {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 99px;
}
.tag-year { background: rgba(14, 109, 194, 0.12); color: var(--marista-blue); }
.tag-class { background: rgba(247, 201, 72, 0.22); color: #8a6913; }

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
