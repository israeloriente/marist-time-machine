<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    message?: string;
    /** Visual treatment: "default" (yellow CTA), "danger" (red CTA). */
    variant?: "default" | "danger";
    confirmLabel?: string;
    cancelLabel?: string;
    /** When set, user must type this word exactly to enable confirm. */
    typeToConfirm?: string;
    /** Optional list of bullets shown above the confirmation input. */
    details?: string[];
    busy?: boolean;
  }>(),
  {
    title: "Tem certeza?",
    message: "",
    variant: "default",
    confirmLabel: "Confirmar",
    cancelLabel: "Cancelar",
    typeToConfirm: "",
    details: () => [],
    busy: false,
  },
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm"): void;
}>();

const typed = ref("");

const canConfirm = computed(() => {
  if (props.busy) return false;
  if (!props.typeToConfirm) return true;
  return typed.value.trim().toUpperCase() === props.typeToConfirm.toUpperCase();
});

function close() {
  if (props.busy) return;
  emit("close");
}

function confirm() {
  if (!canConfirm.value) return;
  emit("confirm");
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return;
  if (e.key === "Escape") close();
  if (e.key === "Enter" && canConfirm.value) confirm();
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      typed.value = "";
      window.addEventListener("keydown", onKey);
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
    <div v-if="open" class="backdrop" @click.self="close">
      <div
        class="dialog"
        :class="`variant-${variant}`"
        role="alertdialog"
        aria-modal="true"
        :aria-labelledby="'confirm-title'"
      >
        <header class="head">
          <h3 id="confirm-title">{{ title }}</h3>
          <button class="close" :disabled="busy" aria-label="Fechar" @click="close">✕</button>
        </header>

        <div class="body">
          <p v-if="message" class="message">{{ message }}</p>

          <ul v-if="details.length" class="details">
            <li v-for="(d, i) in details" :key="i">{{ d }}</li>
          </ul>

          <label v-if="typeToConfirm" class="type-input">
            <span>
              Digite <strong>{{ typeToConfirm }}</strong> para confirmar:
            </span>
            <input
              v-model="typed"
              class="input"
              type="text"
              :placeholder="typeToConfirm"
              autocomplete="off"
              autocapitalize="characters"
              spellcheck="false"
            />
          </label>
        </div>

        <footer class="foot">
          <button type="button" class="button secondary" :disabled="busy" @click="close">
            {{ cancelLabel }}
          </button>
          <button
            type="button"
            class="button"
            :class="{ danger: variant === 'danger' }"
            :disabled="!canConfirm"
            @click="confirm"
          >
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
.dialog.variant-danger {
  border-top: 3px solid var(--error);
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.1rem;
  border-bottom: 1px solid var(--border);
}
.head h3 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--marista-navy);
}
.variant-danger .head h3 { color: var(--error); }

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
  gap: 0.75rem;
}
.message {
  margin: 0;
  line-height: 1.5;
  white-space: pre-wrap;
}

.details {
  list-style: none;
  margin: 0;
  padding: 0.7rem 0.9rem;
  background: var(--surface-strong);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.9rem;
  color: var(--text);
}
.details li {
  display: flex;
  gap: 0.4rem;
  align-items: baseline;
}
.details li::before {
  content: "•";
  color: var(--muted);
  flex-shrink: 0;
}

.type-input {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.25rem;
  font-size: 0.9rem;
  color: var(--muted);
}
.type-input strong {
  color: var(--marista-navy);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.variant-danger .type-input strong { color: var(--error); }

.foot {
  display: flex;
  gap: 0.5rem;
  padding: 0.85rem 1.1rem calc(0.85rem + var(--safe-bottom));
  border-top: 1px solid var(--border);
}
.foot .button { flex: 1; }
.foot .button.danger {
  background: var(--error);
  color: white;
}
.foot .button.danger:hover:not(:disabled) {
  background: #b32f2f;
}

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
