<script setup lang="ts">
import { computed } from "vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import PromptDialog from "@/components/PromptDialog.vue";
import { useNotifyStore } from "@/stores/notify";

const notify = useNotifyStore();

// We only show ONE confirm/prompt at a time (the head of each queue).
// Anything queued behind it shows up after the current one resolves.
const currentConfirm = computed(() => notify.confirmQueue[0] ?? null);
const currentPrompt = computed(() => notify.promptQueue[0] ?? null);
</script>

<template>
  <!-- Toast stack -->
  <div class="toast-stack" role="region" aria-live="polite" aria-label="Notificações">
    <TransitionGroup name="toast">
      <div
        v-for="t in notify.toasts"
        :key="t.id"
        :class="['toast', `toast-${t.variant}`]"
        role="status"
      >
        <span class="icon" aria-hidden="true">
          <template v-if="t.variant === 'success'">✓</template>
          <template v-else-if="t.variant === 'error'">✕</template>
          <template v-else-if="t.variant === 'warning'">!</template>
          <template v-else>i</template>
        </span>
        <span class="msg">{{ t.message }}</span>
        <button
          type="button"
          class="dismiss"
          aria-label="Dispensar"
          @click="notify.dismissToast(t.id)"
        >✕</button>
      </div>
    </TransitionGroup>
  </div>

  <!-- Confirm queue (head only) -->
  <ConfirmDialog
    v-if="currentConfirm"
    :key="currentConfirm.id"
    :open="true"
    :title="currentConfirm.opts.title || 'Tem certeza?'"
    :message="currentConfirm.opts.message || ''"
    :variant="currentConfirm.opts.variant || 'default'"
    :confirm-label="currentConfirm.opts.confirmLabel || 'Confirmar'"
    :cancel-label="currentConfirm.opts.cancelLabel || 'Cancelar'"
    :type-to-confirm="currentConfirm.opts.typeToConfirm || ''"
    :details="currentConfirm.opts.details || []"
    @close="notify.resolveConfirm(currentConfirm.id, false)"
    @confirm="notify.resolveConfirm(currentConfirm.id, true)"
  />

  <!-- Prompt queue (head only) -->
  <PromptDialog
    v-if="currentPrompt"
    :key="currentPrompt.id"
    :open="true"
    :title="currentPrompt.opts.title || ''"
    :message="currentPrompt.opts.message || ''"
    :default-value="currentPrompt.opts.defaultValue || ''"
    :placeholder="currentPrompt.opts.placeholder || ''"
    :confirm-label="currentPrompt.opts.confirmLabel || 'Confirmar'"
    :cancel-label="currentPrompt.opts.cancelLabel || 'Cancelar'"
    :required="!!currentPrompt.opts.required"
    @cancel="notify.resolvePrompt(currentPrompt.id, null)"
    @submit="(v) => notify.resolvePrompt(currentPrompt.id, v)"
  />
</template>

<style scoped>
.toast-stack {
  position: fixed;
  top: calc(0.75rem + var(--safe-top));
  right: 0.75rem;
  left: 0.75rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
  z-index: 1000;
  pointer-events: none;
}
@media (min-width: 640px) {
  .toast-stack {
    left: auto;
    max-width: 420px;
  }
}

.toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.7rem 0.9rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--marista-blue);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(12, 44, 79, 0.15);
  color: var(--text);
  font-size: 0.92rem;
  line-height: 1.4;
}
.toast .icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  font-weight: 700;
  flex-shrink: 0;
  background: var(--marista-blue);
  color: white;
}
.toast .msg { flex: 1; min-width: 0; white-space: pre-wrap; }
.toast .dismiss {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.25rem 0.4rem;
  border-radius: 4px;
}
.toast .dismiss:hover { background: var(--surface-strong); color: var(--text); }

.toast-success { border-left-color: #1f9c52; }
.toast-success .icon { background: #1f9c52; }
.toast-error { border-left-color: var(--error); }
.toast-error .icon { background: var(--error); }
.toast-warning { border-left-color: #c4860e; }
.toast-warning .icon { background: #c4860e; }

.toast-enter-active, .toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.toast-enter-from { opacity: 0; transform: translateY(-12px); }
.toast-leave-to { opacity: 0; transform: translateX(20px); }
</style>
