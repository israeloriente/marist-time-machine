/**
 * Programmatic notify system — toast(), confirm(), prompt(). All native
 * dialogs are banned from the UI; everything goes through this store and
 * is rendered by <NotifyHost /> mounted once in App.vue.
 */
import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastVariant = "info" | "success" | "error" | "warning";

export interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
  /** ms until auto-dismiss; 0 = sticky (manual dismiss only) */
  duration: number;
}

export interface ConfirmOpts {
  title?: string;
  message?: string;
  variant?: "default" | "danger";
  confirmLabel?: string;
  cancelLabel?: string;
  /** When set, user must type this word to enable confirm. */
  typeToConfirm?: string;
  details?: string[];
}

export interface PromptOpts {
  title?: string;
  message?: string;
  /** Default input value */
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Required (non-empty after trim) — disables confirm until typed */
  required?: boolean;
}

interface PendingConfirm {
  id: number;
  opts: ConfirmOpts;
  resolve: (ok: boolean) => void;
}

interface PendingPrompt {
  id: number;
  opts: PromptOpts;
  resolve: (value: string | null) => void;
}

let nextId = 1;

export const useNotifyStore = defineStore("notify", () => {
  const toasts = ref<Toast[]>([]);
  const confirmQueue = ref<PendingConfirm[]>([]);
  const promptQueue = ref<PendingPrompt[]>([]);

  function toast(
    message: string,
    variant: ToastVariant = "info",
    duration = 4000,
  ): number {
    const id = nextId++;
    toasts.value.push({ id, message, variant, duration });
    if (duration > 0) {
      setTimeout(() => dismissToast(id), duration);
    }
    return id;
  }

  function dismissToast(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }

  /** Convenience: error toast formatted from an Axios-like exception. */
  function error(message: string, exc?: unknown): number {
    const detail =
      (exc as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail ??
      (exc as { message?: string })?.message;
    return toast(detail ? `${message}: ${detail}` : message, "error", 6000);
  }

  function success(message: string, duration = 3500): number {
    return toast(message, "success", duration);
  }

  function info(message: string, duration = 4000): number {
    return toast(message, "info", duration);
  }

  function confirm(opts: ConfirmOpts | string): Promise<boolean> {
    const normalized: ConfirmOpts =
      typeof opts === "string" ? { message: opts } : opts;
    return new Promise((resolve) => {
      confirmQueue.value.push({ id: nextId++, opts: normalized, resolve });
    });
  }

  function resolveConfirm(id: number, ok: boolean) {
    const idx = confirmQueue.value.findIndex((c) => c.id === id);
    if (idx < 0) return;
    const item = confirmQueue.value[idx];
    confirmQueue.value.splice(idx, 1);
    item.resolve(ok);
  }

  function prompt(opts: PromptOpts | string): Promise<string | null> {
    const normalized: PromptOpts =
      typeof opts === "string" ? { message: opts } : opts;
    return new Promise((resolve) => {
      promptQueue.value.push({ id: nextId++, opts: normalized, resolve });
    });
  }

  function resolvePrompt(id: number, value: string | null) {
    const idx = promptQueue.value.findIndex((p) => p.id === id);
    if (idx < 0) return;
    const item = promptQueue.value[idx];
    promptQueue.value.splice(idx, 1);
    item.resolve(value);
  }

  return {
    toasts,
    confirmQueue,
    promptQueue,
    toast,
    info,
    success,
    error,
    dismissToast,
    confirm,
    resolveConfirm,
    prompt,
    resolvePrompt,
  };
});
