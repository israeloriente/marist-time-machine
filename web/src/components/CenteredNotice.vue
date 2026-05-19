<script setup lang="ts">
withDefaults(
  defineProps<{
    /** Visual treatment: 'loading' shows a spinner, 'empty' shows the slot icon/emoji. */
    variant?: "loading" | "empty" | "error";
    /** Optional headline above the message. */
    title?: string;
    /** Minimum vertical height of the centered block (px). */
    minHeight?: number;
  }>(),
  {
    variant: "empty",
    title: "",
    minHeight: 280,
  },
);
</script>

<template>
  <div class="centered-notice" :style="{ minHeight: `${minHeight}px` }">
    <div v-if="variant === 'loading'" class="spinner" aria-hidden="true" />
    <h3 v-if="title" class="centered-title">{{ title }}</h3>
    <p class="centered-text">
      <slot />
    </p>
  </div>
</template>

<style scoped>
.centered-notice {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 2rem 1rem;
  text-align: center;
  color: var(--muted);
}
.centered-title {
  margin: 0;
  color: var(--marista-navy);
  font-size: 1rem;
  font-weight: 700;
}
.centered-text {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.5;
  max-width: 480px;
}
.spinner {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 3px solid var(--surface-strong);
  border-top-color: var(--marista-blue);
  animation: spin 0.8s linear infinite;
  margin-bottom: 0.4rem;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
