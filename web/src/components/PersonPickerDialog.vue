<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import FaceThumb from "@/components/FaceThumb.vue";
import { peopleApi, type Person } from "@/services/api";

const PAGE_SIZE = 100;

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    confirmLabel?: string;
    excludeId?: string | null;
    onlyNamed?: boolean;
  }>(),
  {
    title: "Escolher pessoa",
    confirmLabel: "Confirmar",
    excludeId: null,
    onlyNamed: false,
  },
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "pick", person: Person): void;
}>();

const people = ref<Person[]>([]);
const loading = ref(false); // initial page / search reload
const loadingMore = ref(false); // appending next page
const hasMore = ref(false);
const query = ref("");
const selected = ref<Person | null>(null);
const sentinel = ref<HTMLElement | null>(null);

let offset = 0;
// Bumped on every reload() so a slow in-flight request from a previous search
// term can't overwrite results for the current one.
let loadToken = 0;
let searchDebounce: ReturnType<typeof setTimeout> | undefined;
let observer: IntersectionObserver | undefined;

// Server returns a page of PAGE_SIZE; we still drop the excluded id and any
// anonymous people locally (cheap, at most one missing slot per page).
function applyLocalFilter(list: Person[]): Person[] {
  return list
    .filter((p) => p.id !== props.excludeId)
    .filter((p) => (props.onlyNamed ? !!p.display_name : true));
}

async function fetchPage(): Promise<Person[]> {
  const q = query.value.trim();
  return peopleApi.list({
    limit: PAGE_SIZE,
    offset,
    ...(q ? { q } : {}),
  });
}

// Reset and load the first page for the current search term.
async function reload() {
  const token = ++loadToken;
  loading.value = true;
  offset = 0;
  try {
    const list = await fetchPage();
    if (token !== loadToken) return; // stale response, a newer reload won
    people.value = applyLocalFilter(list);
    offset = list.length;
    hasMore.value = list.length === PAGE_SIZE;
  } finally {
    if (token === loadToken) loading.value = false;
  }
  await nextTick();
  observeSentinel();
}

// Append the next page (infinite scroll).
async function loadMore() {
  if (loadingMore.value || loading.value || !hasMore.value) return;
  const token = loadToken;
  loadingMore.value = true;
  try {
    const list = await fetchPage();
    if (token !== loadToken) return; // a reload happened mid-flight
    people.value = people.value.concat(applyLocalFilter(list));
    offset += list.length;
    hasMore.value = list.length === PAGE_SIZE;
  } finally {
    if (token === loadToken) loadingMore.value = false;
  }
  // Re-attach: if the sentinel is still on screen (tall viewport, short page)
  // the observer won't re-fire on its own, so re-observe to keep loading.
  await nextTick();
  observeSentinel();
}

function observeSentinel() {
  observer?.disconnect();
  if (!sentinel.value) return;
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore();
    },
    { threshold: 0.1 },
  );
  observer.observe(sentinel.value);
}

watch(query, () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(reload, 300);
});

function pick(p: Person) {
  selected.value = p;
}

function confirm() {
  if (!selected.value) return;
  emit("pick", selected.value);
}

function close() {
  emit("close");
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return;
  if (e.key === "Escape") close();
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      selected.value = null;
      query.value = "";
      reload();
    } else {
      observer?.disconnect();
    }
  },
);

onMounted(() => {
  window.addEventListener("keydown", onKey);
  if (props.open) reload();
});
onUnmounted(() => {
  window.removeEventListener("keydown", onKey);
  observer?.disconnect();
  clearTimeout(searchDebounce);
});
</script>

<template>
  <Transition name="dialog">
    <div v-if="open" class="dialog-backdrop" @click.self="close">
      <div class="dialog" role="dialog" aria-modal="true">
        <header class="dialog-head">
          <h3>{{ title }}</h3>
          <button class="close-btn" aria-label="Fechar" @click="close">✕</button>
        </header>

        <div class="dialog-body">
          <input
            v-model="query"
            class="input"
            placeholder="Buscar pelo nome…"
            autofocus
          />

          <p v-if="loading" class="muted">Carregando pessoas…</p>
          <p v-else-if="!people.length" class="muted">
            <template v-if="query">Nenhuma pessoa com esse nome.</template>
            <template v-else>Nenhuma outra pessoa disponível.</template>
          </p>

          <template v-else>
            <div class="people-grid">
              <button
                v-for="p in people"
                :key="p.id"
                type="button"
                class="person-card"
                :class="{ active: selected?.id === p.id }"
                @click="pick(p)"
              >
                <FaceThumb
                  v-if="p.thumb_signed_url && p.thumb_bbox"
                  :src="p.thumb_signed_url"
                  :bbox="p.thumb_bbox"
                  :size="72"
                  :padding="0.3"
                />
                <div v-else class="thumb-placeholder">?</div>
                <strong class="name">{{ p.display_name || "Sem nome" }}</strong>
                <span class="muted small">
                  {{ p.face_count }} {{ p.face_count === 1 ? "foto" : "fotos" }}
                </span>
                <span v-if="selected?.id === p.id" class="check">✓</span>
              </button>
            </div>

            <!-- Infinite-scroll trigger: when this enters the viewport we
                 fetch the next page of PAGE_SIZE people. -->
            <div v-if="hasMore" ref="sentinel" class="load-sentinel">
              <span v-if="loadingMore" class="muted small">Carregando mais…</span>
            </div>
          </template>
        </div>

        <footer class="dialog-foot">
          <button type="button" class="button secondary" @click="close">Cancelar</button>
          <button
            type="button"
            class="button"
            :disabled="!selected"
            @click="confirm"
          >
            <template v-if="selected">
              {{ confirmLabel }}: {{ selected.display_name || `Pessoa ${selected.id.slice(0, 8)}` }}
            </template>
            <template v-else>{{ confirmLabel }}</template>
          </button>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(12, 44, 79, 0.55);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 100;
  padding: 0;
}

.dialog {
  background: var(--surface);
  color: var(--text);
  width: 100%;
  max-width: 720px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}

.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 1.1rem;
  border-bottom: 1px solid var(--border);
}
.dialog-head h3 {
  margin: 0;
  font-size: 1.1rem;
}
.close-btn {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--muted);
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
}
.close-btn:hover { background: var(--surface-strong); color: var(--text); }

.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.people-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.6rem;
}
.load-sentinel {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 40px;
  padding: 0.6rem 0;
}
.person-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 0.7rem 0.4rem;
  background: var(--surface);
  border: 2px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  text-align: center;
  position: relative;
  font: inherit;
  color: var(--text);
  transition: border-color 0.15s, background 0.15s;
}
.person-card:hover { border-color: var(--marista-blue); }
.person-card.active {
  border-color: var(--marista-yellow);
  background: rgba(247, 201, 72, 0.1);
}
.person-card .check {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
}
.thumb-placeholder {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  background: var(--surface-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-size: 1.4rem;
}
.name {
  font-size: 0.85rem;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--marista-navy);
}
.small { font-size: 0.75rem; }

.dialog-foot {
  padding: 0.85rem 1.1rem calc(0.85rem + var(--safe-bottom));
  border-top: 1px solid var(--border);
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
.dialog-foot .button {
  flex: 1;
}

@media (min-width: 720px) {
  .dialog-backdrop { align-items: center; padding: 2rem 1rem; }
  .dialog { border-radius: 16px; max-height: 80vh; }
  .dialog-foot .button { flex: 0 0 auto; min-width: 180px; }
}

/* Transition */
.dialog-enter-active, .dialog-leave-active { transition: opacity 0.15s ease; }
.dialog-enter-active .dialog,
.dialog-leave-active .dialog { transition: transform 0.2s ease; }
.dialog-enter-from, .dialog-leave-to { opacity: 0; }
.dialog-enter-from .dialog, .dialog-leave-to .dialog { transform: translateY(20px); }
</style>
