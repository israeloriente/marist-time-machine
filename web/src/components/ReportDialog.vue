<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { reportsApi } from "@/services/api";
import { useNotifyStore } from "@/stores/notify";

const props = defineProps<{
  open: boolean;
  photoId?: string | null;
  faceId?: string | null;
  thumbUrl?: string | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submitted"): void;
}>();

const reason = ref("");
const contact = ref("");
const busy = ref(false);
const notify = useNotifyStore();
const textareaEl = ref<HTMLTextAreaElement | null>(null);

const canSubmit = computed(() => !busy.value && reason.value.trim().length >= 5);

function cancel() {
  if (busy.value) return;
  emit("close");
}

async function submit() {
  if (!canSubmit.value) return;
  busy.value = true;
  try {
    await reportsApi.create({
      photo_id: props.photoId ?? undefined,
      face_id: props.faceId ?? undefined,
      reason: reason.value.trim(),
      contact_info: contact.value.trim() || undefined,
    });
    notify.success("Denúncia enviada. Um admin vai avaliar em breve.");
    emit("submitted");
    emit("close");
  } catch (e) {
    notify.error("Não foi possível enviar a denúncia", e);
  } finally {
    busy.value = false;
  }
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return;
  if (e.key === "Escape") cancel();
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      reason.value = "";
      contact.value = "";
      window.addEventListener("keydown", onKey);
      nextTick(() => textareaEl.value?.focus());
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
        <header class="head">
          <h3>Denunciar esta mídia</h3>
          <button class="close" :disabled="busy" aria-label="Fechar" @click="cancel">✕</button>
        </header>

        <div class="body">
          <div v-if="thumbUrl" class="thumb">
            <img :src="thumbUrl" alt="" />
          </div>

          <p class="lead">
            Está nessa foto/vídeo e gostaria de removê-la? Conta o motivo
            pra gente. A denúncia vai pra um administrador avaliar.
          </p>

          <label>
            <span>Motivo <em>*</em></span>
            <textarea
              ref="textareaEl"
              v-model="reason"
              class="input"
              rows="4"
              placeholder="Ex: apareço nessa foto e quero removê-la, ou: foto inadequada, etc."
              :disabled="busy"
              maxlength="2000"
            />
          </label>

          <label>
            <span>Contato (opcional)</span>
            <input
              v-model="contact"
              class="input"
              placeholder="E-mail ou telefone, se quiser retorno"
              :disabled="busy"
              maxlength="300"
            />
          </label>
        </div>

        <footer class="foot">
          <button type="button" class="button secondary" :disabled="busy" @click="cancel">
            Cancelar
          </button>
          <button type="button" class="button" :disabled="!canSubmit" @click="submit">
            <template v-if="busy">Enviando…</template>
            <template v-else>Enviar denúncia</template>
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
  z-index: 110;
}
.dialog {
  background: var(--surface);
  color: var(--text);
  width: 100%;
  max-width: 520px;
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

.body {
  padding: 1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  max-height: 70vh;
  overflow-y: auto;
}
.thumb {
  width: 100%;
  height: 130px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-strong);
}
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.lead { margin: 0; line-height: 1.5; color: var(--text); }

.body label {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.88rem;
  color: var(--muted);
}
.body em { color: var(--error); font-style: normal; }
.body textarea {
  resize: vertical;
  min-height: 90px;
  font-family: inherit;
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
