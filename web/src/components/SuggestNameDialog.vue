<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useProfileStore } from "@/stores/profile";

const props = defineProps<{
  open: boolean;
  targetLabel?: string;       // "essa pessoa" / "esse rosto"
  thumbSrc?: string;
  alreadySuggested?: string;  // shows hint if user already suggested before
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: { name: string; year: number | null; class_letter: string | null }): void;
}>();

const profileStore = useProfileStore();

const currentYear = new Date().getFullYear();
const graduationYears = Array.from({ length: 111 }, (_, i) => currentYear + 10 - i);
const classes = ["A", "B", "C", "D", "E", "F"];

const name = ref("");
const year = ref<number | "">("");
const klass = ref<string>("");

const canSubmit = computed(() => name.value.trim().length >= 2);

function submit() {
  if (!canSubmit.value) return;
  emit("submit", {
    name: name.value.trim(),
    year: year.value === "" ? null : (year.value as number),
    class_letter: klass.value || null,
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

          <div class="grad-row">
            <label>
              <span>Ano de formatura</span>
              <select v-model.number="year" class="input">
                <option value="">— Não sei</option>
                <option v-for="y in graduationYears" :key="y" :value="y">{{ y }}</option>
              </select>
            </label>
            <label>
              <span>Turma</span>
              <select v-model="klass" class="input">
                <option value="">— Não sei</option>
                <option v-for="c in classes" :key="c" :value="c">{{ c }}</option>
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
