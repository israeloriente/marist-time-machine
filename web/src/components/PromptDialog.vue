<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    message?: string;
    defaultValue?: string;
    placeholder?: string;
    confirmLabel?: string;
    cancelLabel?: string;
    required?: boolean;
    busy?: boolean;
  }>(),
  {
    title: "",
    message: "",
    defaultValue: "",
    placeholder: "",
    confirmLabel: "Confirmar",
    cancelLabel: "Cancelar",
    required: false,
    busy: false,
  },
);

const emit = defineEmits<{
  (e: "cancel"): void;
  (e: "submit", value: string): void;
}>();

const value = ref(props.defaultValue);
const inputEl = ref<HTMLInputElement | null>(null);

const canSubmit = computed(() => {
  if (props.busy) return false;
  if (!props.required) return true;
  return value.value.trim().length > 0;
});

function cancel() {
  if (props.busy) return;
  emit("cancel");
}

function submit() {
  if (!canSubmit.value) return;
  emit("submit", value.value.trim());
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return;
  if (e.key === "Escape") cancel();
  if (e.key === "Enter" && canSubmit.value) submit();
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      value.value = props.defaultValue;
      window.addEventListener("keydown", onKey);
      // Autofocus once the transition mounts the input
      nextTick(() => {
        inputEl.value?.focus();
        inputEl.value?.select();
      });
    } else {
      window.removeEventListener("keydown", onKey);
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <Transition name="dialog">
    <div v-if="open" class="backdrop" @click.self="cancel">
      <div class="dialog" role="dialog" aria-modal="true">
        <header v-if="title" class="head">
          <h3>{{ title }}</h3>
          <button class="close" :disabled="busy" aria-label="Fechar" @click="cancel">✕</button>
        </header>

        <div class="body">
          <p v-if="message" class="message">{{ message }}</p>
          <input
            ref="inputEl"
            v-model="value"
            class="input"
            type="text"
            :placeholder="placeholder"
            :disabled="busy"
            autocomplete="off"
            @keydown.enter.prevent="submit"
          />
        </div>

        <footer class="foot">
          <button type="button" class="button secondary" :disabled="busy" @click="cancel">
            {{ cancelLabel }}
          </button>
          <button type="button" class="button" :disabled="!canSubmit" @click="submit">
            <template v-if="busy">Processando…</template>
            <template v-else>{{ confirmLabel }}</template>
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
  max-width: 500px;
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
.head h3 { margin: 0; font-size: 1.05rem; color: var(--marista-navy); }
.close {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 1rem;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
}
.close:hover:not(:disabled) { background: var(--surface-strong); color: var(--text); }
.close:disabled { opacity: 0.5; cursor: not-allowed; }

.body {
  padding: 1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.message { margin: 0; line-height: 1.5; white-space: pre-wrap; }
.input { width: 100%; }

.foot {
  display: flex;
  gap: 0.5rem;
  padding: 0.85rem 1.1rem calc(0.85rem + var(--safe-bottom));
  border-top: 1px solid var(--border);
}
.foot .button { flex: 1; }

@media (min-width: 640px) {
  .backdrop { align-items: center; padding: 2rem 1rem; }
  .dialog { border-radius: 16px; }
  .foot { justify-content: flex-end; }
  .foot .button { flex: 0 0 auto; min-width: 130px; }
}

.dialog-enter-active, .dialog-leave-active { transition: opacity 0.15s ease; }
.dialog-enter-active .dialog,
.dialog-leave-active .dialog { transition: transform 0.2s ease; }
.dialog-enter-from, .dialog-leave-to { opacity: 0; }
.dialog-enter-from .dialog, .dialog-leave-to .dialog { transform: translateY(20px); }
</style>
