<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import CenteredNotice from "@/components/CenteredNotice.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import SongCard from "@/components/SongCard.vue";
import { peopleApi, songsApi, type AvailableFilters, type Song } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { useNotifyStore } from "@/stores/notify";

const auth = useAuthStore();
const notify = useNotifyStore();

const songs = ref<Song[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const url = ref("");
const caption = ref("");
const adding = ref(false);
const addError = ref<string | null>(null);

const year = ref<number | "">("");
const onlyMine = ref(false);
const available = ref<AvailableFilters>({ years: [], classes: [] });

const currentUserId = computed(() => auth.session?.user?.id ?? null);

interface Group {
  key: string;
  year: number | null;
  songs: Song[];
}

const grouped = computed<Group[]>(() => {
  const buckets = new Map<string, Group>();
  for (const s of songs.value) {
    const y = s.user_graduation_year;
    const key = String(y ?? "");
    if (!buckets.has(key)) {
      buckets.set(key, { key, year: y, songs: [] });
    }
    buckets.get(key)!.songs.push(s);
  }
  // Order: defined year first (most recent first), undefined at the end.
  return Array.from(buckets.values()).sort((a, b) => {
    if (a.year == null && b.year != null) return 1;
    if (b.year == null && a.year != null) return -1;
    return (b.year ?? 0) - (a.year ?? 0);
  });
});

function groupLabel(g: Group) {
  if (g.year == null) return "Sem ano informado";
  return `Turma de ${g.year}`;
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const filters: { year?: number; user_id?: string } = {};
    if (year.value !== "") filters.year = year.value;
    if (onlyMine.value && currentUserId.value) filters.user_id = currentUserId.value;
    songs.value = await songsApi.list(filters);
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    loading.value = false;
  }
}

async function loadFilters() {
  try {
    available.value = await peopleApi.filters();
  } catch {
    /* silent */
  }
}

async function addSong() {
  if (!url.value.trim()) return;
  adding.value = true;
  addError.value = null;
  try {
    await songsApi.create(url.value.trim(), caption.value.trim() || undefined);
    url.value = "";
    caption.value = "";
    await load();
  } catch (e: any) {
    addError.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    adding.value = false;
  }
}

const removeTarget = ref<Song | null>(null);
const removing = ref(false);
function askRemove(id: string) {
  removeTarget.value = songs.value.find((s) => s.id === id) ?? null;
}
function cancelRemove() {
  if (removing.value) return;
  removeTarget.value = null;
}
async function confirmRemove() {
  const target = removeTarget.value;
  if (!target) return;
  removing.value = true;
  try {
    await songsApi.remove(target.id);
    songs.value = songs.value.filter((s) => s.id !== target.id);
    removeTarget.value = null;
  } catch (e: any) {
    notify.error("Erro ao remover música", e);
  } finally {
    removing.value = false;
  }
}

watch([year, onlyMine], load);

onMounted(async () => {
  await Promise.all([loadFilters(), load()]);
});
</script>

<template>
  <section class="hero songs-hero">
    <span class="kicker">Trilha sonora Marista</span>
    <h1>Músicas que marcaram</h1>
    <p>
      Compartilhe as músicas que tocaram durante seus anos no colégio. Festas, formaturas,
      ensaios e principalmente toques do intervalo — adicione com a URL do YouTube.
    </p>
  </section>

  <!-- Add form -->
  <section class="card add-form">
    <h3>Adicionar uma música</h3>
    <div class="form-row">
      <input
        v-model="url"
        class="input"
        placeholder="Cole a URL do YouTube (ex: youtu.be/xxxxxxx)"
        :disabled="adding"
        @keydown.enter="addSong"
      />
      <input
        v-model="caption"
        class="input"
        placeholder="O que essa música te lembra? (opcional)"
        :disabled="adding"
        @keydown.enter="addSong"
      />
      <button class="button" :disabled="adding || !url.trim()" @click="addSong">
        {{ adding ? "Adicionando…" : "Adicionar" }}
      </button>
    </div>
    <p v-if="addError" class="error">{{ addError }}</p>
  </section>

  <!-- Filters -->
  <section class="filters">
    <select v-model.number="year" class="input">
      <option value="">Todos os anos</option>
      <option v-for="y in available.years" :key="y" :value="y">{{ y }}</option>
    </select>
    <label class="checkbox">
      <input v-model="onlyMine" type="checkbox" />
      <span>Só minhas</span>
    </label>
  </section>

  <CenteredNotice v-if="loading" variant="loading">Carregando…</CenteredNotice>
  <CenteredNotice v-else-if="error" variant="error">{{ error }}</CenteredNotice>
  <CenteredNotice v-else-if="!songs.length" variant="empty">
    Ainda não tem música por aqui. Cole uma URL acima pra começar.
  </CenteredNotice>

  <div v-else class="groups">
    <section v-for="g in grouped" :key="g.key" class="group">
      <header class="group-head">
        <h2>{{ groupLabel(g) }}</h2>
        <span class="muted small">{{ g.songs.length }} {{ g.songs.length === 1 ? "música" : "músicas" }}</span>
      </header>
      <div class="songs-grid">
        <SongCard
          v-for="s in g.songs"
          :key="s.id"
          :song="s"
          :can-remove="s.user_id === currentUserId"
          @remove="askRemove"
        />
      </div>
    </section>
  </div>

  <ConfirmDialog
    :open="removeTarget !== null"
    :title="'Remover esta música?'"
    :message="removeTarget?.title || 'Vídeo do YouTube'"
    :confirm-label="'Remover'"
    variant="danger"
    :busy="removing"
    @close="cancelRemove"
    @confirm="confirmRemove"
  />
</template>

<style scoped>
.songs-hero {
  margin-bottom: 1.25rem;
  position: relative;
  overflow: hidden;
}
.kicker {
  display: inline-block;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.85rem;
}
.songs-hero h1 {
  color: var(--text-on-dark);
  margin: 0 0 0.5rem;
  font-size: 1.8rem;
}
.songs-hero p {
  color: var(--muted-on-dark);
  margin: 0;
  max-width: 560px;
}

.add-form { padding: 1rem 1.1rem; margin-bottom: 1rem; }
.add-form h3 { margin: 0 0 0.6rem; font-size: 1rem; }
.form-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
}
@media (min-width: 720px) {
  .form-row {
    grid-template-columns: 1.4fr 1fr max-content;
    align-items: end;
  }
}

.filters {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
  align-items: center;
}
.checkbox {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  color: var(--text);
  white-space: nowrap;
}
@media (max-width: 480px) {
  .filters { grid-template-columns: 1fr; }
}

.groups { display: flex; flex-direction: column; gap: 1.5rem; }
.group-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.4rem;
}
.group-head h2 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--marista-navy);
}

.songs-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.85rem;
}
@media (min-width: 640px) {
  .songs-grid { grid-template-columns: 1fr 1fr; }
}
@media (min-width: 1024px) {
  .songs-grid { grid-template-columns: 1fr 1fr 1fr; }
}

.error { color: var(--error); }
.small { font-size: 0.8rem; }
</style>
