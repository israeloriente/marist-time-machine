<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import CenteredNotice from "@/components/CenteredNotice.vue";
import FaceThumb from "@/components/FaceThumb.vue";
import { peopleApi, type AvailableFilters, type Person } from "@/services/api";
import { formatCollabRange } from "@/constants/people";
import { useNotifyStore } from "@/stores/notify";

const notify = useNotifyStore();

const router = useRouter();

const people = ref<Person[]>([]);
const loading = ref(true);

const query = ref("");
const year = ref<number | "">("");
const klass = ref<string>("");
const status = ref<"active" | "rejected">("active");
const available = ref<AvailableFilters>({ years: [], classes: [] });

// Drag state
const draggingId = ref<string | null>(null);
const dropTargetId = ref<string | null>(null);
const merging = ref(false);

async function loadFilters() {
  try {
    available.value = await peopleApi.filters();
  } catch {
    /* silent */
  }
}

async function load() {
  loading.value = true;
  try {
    const filters: { year?: number; class?: string; status?: "active" | "rejected" } = {
      status: status.value,
    };
    if (year.value !== "") filters.year = year.value;
    if (klass.value) filters.class = klass.value;
    // Thumbnails come embedded in the list response (thumb_signed_url +
    // thumb_bbox), so no per-person /faces requests are needed here.
    people.value = await peopleApi.list(filters);
  } finally {
    loading.value = false;
  }
}

const filtered = computed(() => {
  if (!query.value.trim()) return people.value;
  const q = query.value.toLowerCase();
  return people.value.filter((p) => (p.display_name ?? "").toLowerCase().includes(q));
});

function clearFilters() {
  year.value = "";
  klass.value = "";
  query.value = "";
}

const hasFilters = computed(() => year.value !== "" || klass.value !== "" || query.value !== "");

// ---------- Drag-and-drop merge (desktop only) ----------

function onDragStart(p: Person, e: DragEvent) {
  if (merging.value) return;
  draggingId.value = p.id;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/x-person-id", p.id);
  }
}

function onDragEnd() {
  draggingId.value = null;
  dropTargetId.value = null;
}

function onDragOver(target: Person, e: DragEvent) {
  if (!draggingId.value || draggingId.value === target.id) return;
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
}

function onDragEnter(target: Person) {
  if (!draggingId.value || draggingId.value === target.id) return;
  dropTargetId.value = target.id;
}

function onDragLeave(target: Person, e: DragEvent) {
  // Only clear if we actually left the element (not a child)
  const related = e.relatedTarget as Node | null;
  const currentTarget = e.currentTarget as Node | null;
  if (currentTarget && related && currentTarget.contains(related)) return;
  if (dropTargetId.value === target.id) dropTargetId.value = null;
}

async function onDrop(target: Person, e: DragEvent) {
  e.preventDefault();
  const sourceId = draggingId.value || e.dataTransfer?.getData("text/x-person-id");
  draggingId.value = null;
  dropTargetId.value = null;
  if (!sourceId || sourceId === target.id) return;

  const source = people.value.find((p) => p.id === sourceId);
  if (!source) return;

  const sourceLabel = source.display_name || `Pessoa ${source.id.slice(0, 8)}`;
  const targetLabel = target.display_name || `Pessoa ${target.id.slice(0, 8)}`;
  const ok = await notify.confirm({
    title: "Mesclar pessoas?",
    message: `"${sourceLabel}" será mesclada em "${targetLabel}". ${source.face_count} rostos serão movidos e "${sourceLabel}" será apagada.`,
    confirmLabel: "Mesclar",
    variant: "danger",
  });
  if (!ok) return;

  merging.value = true;
  try {
    await peopleApi.merge(sourceId, target.id);
    people.value = people.value
      .map((p) =>
        p.id === target.id
          ? { ...p, face_count: p.face_count + source.face_count }
          : p,
      )
      .filter((p) => p.id !== sourceId);
  } catch (err) {
    notify.error("Erro ao mesclar", err);
    await load();
  } finally {
    merging.value = false;
  }
}

function goToPerson(p: Person, e: MouseEvent) {
  // Ignore clicks that came from a drag operation
  if (draggingId.value) return;
  // Mouse middle / cmd-click open in new tab — let browser handle
  if (e.metaKey || e.ctrlKey || e.button === 1) return;
  router.push({ name: "person", params: { id: p.id } });
}

async function reactivatePerson(p: Person, e: MouseEvent) {
  e.stopPropagation();
  try {
    await peopleApi.setStatus(p.id, "active");
    people.value = people.value.filter((x) => x.id !== p.id);
    notify.success("Pessoa reativada");
  } catch (err) {
    notify.error("Erro ao reativar pessoa", err);
  }
}

watch([year, klass, status], load);

onMounted(async () => {
  await Promise.all([loadFilters(), load()]);
});
</script>

<template>
  <header class="page-header">
    <div>
      <h1>Pessoas</h1>
      <p class="muted">
        Filtre por ano/turma das fotos onde aparecem.
        <span class="hint hide-on-mobile">
          💡 Arraste uma pessoa em cima de outra pra mesclar.
        </span>
      </p>
    </div>
  </header>

  <div class="tabs">
    <button :class="{ active: status === 'active' }" @click="status = 'active'">
      Ativas
    </button>
    <button :class="{ active: status === 'rejected' }" @click="status = 'rejected'">
      Rejeitadas
    </button>
  </div>

  <section class="filters card">
    <div class="filter-grid">
      <label>
        <span>Buscar por nome</span>
        <input v-model="query" class="input" placeholder="Digite um nome…" />
      </label>
      <label>
        <span>Ano de formatura</span>
        <select v-model.number="year" class="input">
          <option value="">Todos os anos</option>
          <option v-for="y in available.years" :key="y" :value="y">{{ y }}</option>
        </select>
      </label>
      <label>
        <span>Turma</span>
        <select v-model="klass" class="input">
          <option value="">Todas as turmas</option>
          <option v-for="c in available.classes" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <button
        v-if="hasFilters"
        class="button secondary clear-btn"
        type="button"
        @click="clearFilters"
      >
        Limpar
      </button>
    </div>
  </section>

  <CenteredNotice v-if="loading" variant="loading">Carregando…</CenteredNotice>
  <CenteredNotice v-else-if="!filtered.length" variant="empty">
    <template v-if="hasFilters">Nenhuma pessoa nessa combinação de filtros.</template>
    <template v-else>
      Nenhuma pessoa ainda. Suba mais fotos ou rode "Reagrupar agora" no painel.
    </template>
  </CenteredNotice>
  <div v-else>
    <p class="muted small results-count">
      {{ filtered.length }} {{ filtered.length === 1 ? "pessoa" : "pessoas" }}
    </p>
    <div class="people-grid">
      <div
        v-for="p in filtered"
        :key="p.id"
        :class="[
          'person-card',
          { dragging: draggingId === p.id, 'drop-target': dropTargetId === p.id },
        ]"
        :draggable="!merging"
        :title="p.display_name || 'Sem nome'"
        @click="goToPerson(p, $event)"
        @dragstart="onDragStart(p, $event)"
        @dragend="onDragEnd"
        @dragover="onDragOver(p, $event)"
        @dragenter.prevent="onDragEnter(p)"
        @dragleave="onDragLeave(p, $event)"
        @drop="onDrop(p, $event)"
      >
        <FaceThumb
          v-if="p.thumb_signed_url && p.thumb_bbox"
          :src="p.thumb_signed_url"
          :bbox="p.thumb_bbox"
          :size="96"
          :padding="0.3"
        />
        <div v-else class="thumb-placeholder">?</div>
        <strong class="name">{{ p.display_name || "Sem nome" }}</strong>
        <span class="muted small">{{ p.face_count }} {{ p.face_count === 1 ? "foto" : "fotos" }}</span>
        <!-- Mostra o ano/turma canônicos da pessoa (curados). Colaboradores
             usam faixa de anos. Só cai pros valores derivados das fotos
             quando não há nada canônico. -->
        <div
          v-if="p.person_type === 'collaborator'"
          class="meta-tags"
        >
          <span class="tag tag-collab">
            Colaborador<template v-if="formatCollabRange(p.entry_year, p.exit_year)">
              · {{ formatCollabRange(p.entry_year, p.exit_year) }}</template>
          </span>
        </div>
        <div
          v-else-if="p.graduation_year != null || p.class_letter"
          class="meta-tags"
        >
          <span v-if="p.graduation_year != null" class="tag tag-year">
            {{ p.graduation_year }}
          </span>
          <span v-if="p.class_letter" class="tag tag-class">{{ p.class_letter }}</span>
        </div>
        <div v-else-if="p.graduation_years?.length || p.classes?.length" class="meta-tags">
          <span v-for="y in p.graduation_years" :key="`y-${y}`" class="tag tag-year derived">{{ y }}</span>
          <span v-for="c in p.classes" :key="`c-${c}`" class="tag tag-class derived">{{ c }}</span>
        </div>
        <button
          v-if="status === 'rejected'"
          type="button"
          class="button small reactivate"
          @click="reactivatePerson(p, $event)"
        >↺ Reativar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 1rem; }
.page-header h1 { margin: 0; }
.page-header p { margin: 0.2rem 0 0; }
.hint {
  display: inline-block;
  margin-left: 0.4rem;
  color: var(--marista-blue);
  font-size: 0.85rem;
}
.hide-on-mobile { display: none; }
@media (min-width: 768px) {
  .hide-on-mobile { display: inline; }
}

.filters {
  margin-bottom: 1.25rem;
  padding: 1rem;
}
.filter-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  align-items: end;
}
.filter-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--muted);
}
.clear-btn { align-self: stretch; }
@media (min-width: 640px) {
  .filter-grid {
    grid-template-columns: 2fr 1fr 1fr max-content;
  }
}

.results-count { margin: 0 0 0.6rem; }

.people-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 0.75rem;
}
.person-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.45rem;
  padding: 0.85rem 0.6rem;
  background: var(--surface);
  border: 2px solid var(--border);
  border-radius: 12px;
  text-decoration: none;
  color: var(--text);
  text-align: center;
  cursor: pointer;
  user-select: none;
  transition: border-color 0.15s, transform 0.1s, box-shadow 0.15s;
}
.person-card:hover { border-color: var(--marista-blue); }
.person-card.dragging {
  opacity: 0.5;
  transform: scale(0.96);
}
.person-card.drop-target {
  border-color: var(--marista-yellow);
  border-style: dashed;
  background: rgba(247, 201, 72, 0.15);
  transform: scale(1.04);
  box-shadow: 0 4px 16px rgba(247, 201, 72, 0.35);
}
.thumb-placeholder {
  width: 96px; height: 96px;
  border-radius: 8px;
  background: var(--surface-strong);
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 1.8rem;
}
.name {
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  color: var(--marista-navy);
}
.small { font-size: 0.78rem; }

.meta-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.25rem;
  margin-top: 0.2rem;
}
.tag {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.45rem;
  border-radius: 99px;
  letter-spacing: 0.02em;
}
.tag-year {
  background: rgba(14, 109, 194, 0.12);
  color: var(--marista-blue);
}
.tag-class {
  background: rgba(247, 201, 72, 0.18);
  color: #8a6913;
}
.tag-collab {
  background: rgba(124, 58, 237, 0.14);
  color: #6d28d9;
}
/* Derivado das fotos (estimativa) — apagado, com tracinho indicando que
   não é o cadastro canônico da pessoa. */
.tag.derived {
  background: var(--surface-strong);
  color: var(--muted);
  border: 1px dashed var(--border);
  font-weight: 600;
}

.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border);
  margin: 0 0 1rem;
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

.button.small.reactivate {
  margin-top: 0.4rem;
  min-height: 32px;
  padding: 0.25rem 0.7rem;
  font-size: 0.78rem;
}
</style>
