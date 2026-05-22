<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useProfileStore } from "@/stores/profile";
import { CLASS_LETTERS, collabYears, graduationYears } from "@/constants/people";

const props = defineProps<{
  open: boolean;
  targetLabel?: string;       // "essa pessoa" / "esse rosto"
  thumbSrc?: string;
  alreadySuggested?: string;  // shows hint if user already suggested before
}>();

type PersonType = "student" | "collaborator";

const emit = defineEmits<{
  (e: "close"): void;
  (
    e: "submit",
    payload: {
      name: string;
      person_type: PersonType;
      year: number | null;
      class_letter: string | null;
      entry_year: number | null;
      exit_year: number | null;
    },
  ): void;
}>();

const profileStore = useProfileStore();

const years = graduationYears();
const collabYearsList = collabYears();

const personType = ref<PersonType>("student");
const name = ref("");
const year = ref<number | "">("");
const klass = ref<string>("");
const entryYear = ref<number | "">("");
const exitYear = ref<number | "">("");

const canSubmit = computed(() => name.value.trim().length >= 2);

function submit() {
  if (!canSubmit.value) return;
  const isCollab = personType.value === "collaborator";
  emit("submit", {
    name: name.value.trim(),
    person_type: personType.value,
    year: isCollab || year.value === "" ? null : (year.value as number),
    class_letter: isCollab ? null : klass.value || null,
    entry_year: !isCollab || entryYear.value === "" ? null : (entryYear.value as number),
    exit_year: !isCollab || exitYear.value === "" ? null : (exitYear.value as number),
  });
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
  async (v) => {
    if (!v) return;
    name.value = "";
    personType.value = "student";
    entryYear.value = "";
    exitYear.value = "";
    // Pre-fill year/class with the contributor's own profile — most of the
    // time people identify peers from the same class.
    await profileStore.load();
    year.value = profileStore.profile?.graduation_year ?? "";
    klass.value = profileStore.profile?.class_letter ?? "";
    window.addEventListener("keydown", onKey);
  },
);
watch(
  () => props.open,
  (v) => {
    if (!v) window.removeEventListener("keydown", onKey);
  },
);
</script>

<template>
  <Transition name="dialog">
    <div v-if="open" class="backdrop" @click.self="close">
      <div class="dialog" role="dialog" aria-modal="true">
        <header class="head">
          <h3>Sugerir nome</h3>
          <button class="close" aria-label="Fechar" @click="close">✕</button>
        </header>

        <div class="body">
          <p v-if="alreadySuggested" class="muted small">
            Você já sugeriu "<strong>{{ alreadySuggested }}</strong>" antes. Pode mandar outro nome
            diferente se mudou de ideia.
          </p>

          <label>
            <span>Nome completo <em>*</em></span>
            <input
              v-model="name"
              class="input"
              type="text"
              placeholder="Ex: João Silva"
              autofocus
              @keydown.enter="submit"
            />
          </label>

          <div class="type-toggle" role="group" aria-label="Tipo de pessoa">
            <button
              type="button"
              :class="{ active: personType === 'student' }"
              @click="personType = 'student'"
            >
              Aluno(a)
            </button>
            <button
              type="button"
              :class="{ active: personType === 'collaborator' }"
              @click="personType = 'collaborator'"
            >
              Colaborador(a)
            </button>
          </div>

          <!-- Aluno: ano de formatura + turma -->
          <div v-if="personType === 'student'" class="grad-row">
            <label>
              <span>Ano de formatura</span>
              <select v-model.number="year" class="input">
                <option value="">— Não sei</option>
                <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
              </select>
            </label>
            <label>
              <span>Turma</span>
              <select v-model="klass" class="input">
                <option value="">— Não sei</option>
                <option v-for="c in CLASS_LETTERS" :key="c" :value="c">{{ c }}</option>
              </select>
            </label>
          </div>

          <!-- Colaborador: faixa de anos (entrada–saída), ambos opcionais -->
          <div v-else class="grad-row">
            <label>
              <span>Ano de entrada</span>
              <select v-model.number="entryYear" class="input">
                <option value="">— Não sei</option>
                <option v-for="y in collabYearsList" :key="y" :value="y">{{ y }}</option>
              </select>
            </label>
            <label>
              <span>Ano de saída</span>
              <select v-model.number="exitYear" class="input">
                <option value="">— Não sei / ainda atua</option>
                <option v-for="y in collabYearsList" :key="y" :value="y">{{ y }}</option>
              </select>
            </label>
          </div>
          <p class="muted small hint">
            Suas sugestões passam por revisão antes de entrarem na base.
          </p>
        </div>

        <footer class="foot">
          <button type="button" class="button secondary" @click="close">Cancelar</button>
          <button type="button" class="button" :disabled="!canSubmit" @click="submit">
            Enviar sugestão
          </button>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(12, 44, 79, 0.55);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 100;
}
.dialog {
  background: var(--surface);
  color: var(--text);
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.1rem;
  border-bottom: 1px solid var(--border);
}
.head h3 { margin: 0; font-size: 1.1rem; }
.close {
  background: none; border: none; color: var(--muted);
  cursor: pointer; font-size: 1.1rem; padding: 0.3rem 0.6rem; border-radius: 6px;
}
.close:hover { background: var(--surface-strong); color: var(--text); }

.body {
  flex: 1; overflow-y: auto;
  padding: 1rem 1.1rem;
  display: flex; flex-direction: column; gap: 0.8rem;
}
.body label {
  display: flex; flex-direction: column; gap: 0.3rem;
  color: var(--muted); font-size: 0.85rem;
}
.body em { color: var(--marista-yellow); font-style: normal; }
.grad-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
.hint { margin: 0; }

.type-toggle {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}
.type-toggle button {
  background: var(--surface-strong);
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 8px;
  padding: 0.55rem 0.5rem;
  font: inherit;
  font-size: 0.9rem;
  cursor: pointer;
  min-height: 44px;
}
.type-toggle button.active {
  background: rgba(247, 201, 72, 0.18);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}

.foot {
  display: flex;
  gap: 0.5rem;
  padding: 0.85rem 1.1rem calc(0.85rem + var(--safe-bottom));
  border-top: 1px solid var(--border);
}
.foot .button { flex: 1; }

@media (min-width: 640px) {
  .backdrop { align-items: center; padding: 2rem 1rem; }
  .dialog { border-radius: 16px; max-height: 80vh; }
  .foot { justify-content: flex-end; }
  .foot .button { flex: 0 0 auto; min-width: 160px; }
}

.dialog-enter-active, .dialog-leave-active { transition: opacity 0.15s ease; }
.dialog-enter-active .dialog,
.dialog-leave-active .dialog { transition: transform 0.2s ease; }
.dialog-enter-from, .dialog-leave-to { opacity: 0; }
.dialog-enter-from .dialog, .dialog-leave-to .dialog { transform: translateY(20px); }
</style>
