<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useProfileStore } from "@/stores/profile";

const router = useRouter();
const route = useRoute();
const profileStore = useProfileStore();

const currentYear = new Date().getFullYear();
const graduationYears = Array.from({ length: 111 }, (_, i) => currentYear + 10 - i);
const classes = ["A", "B", "C", "D", "E", "F"];

const year = ref<number | "">("");
const klass = ref<string>("");
const saving = ref(false);
const error = ref<string | null>(null);

const canSubmit = computed(() => year.value !== "" && klass.value !== "" && !saving.value);

async function submit() {
  if (!canSubmit.value) return;
  saving.value = true;
  error.value = null;
  try {
    await profileStore.save(year.value as number, klass.value);
    const redirect = (route.query.redirect as string) || "/";
    router.push(redirect);
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await profileStore.load();
  // If user already has profile, send away.
  if (profileStore.profile) {
    const redirect = (route.query.redirect as string) || "/";
    router.replace(redirect);
  }
});
</script>

<template>
  <section class="hero onboarding">
    <span class="kicker">Bem-vindo!</span>
    <h1>Conte sobre você</h1>
    <p>Esses dados ajudam a Cápsula do Tempo a achar fotos da sua turma.</p>

    <form class="form" @submit.prevent="submit">
      <label>
        <span>Ano de formatura <em>*</em></span>
        <select v-model.number="year" class="input" required>
          <option value="" disabled>Selecione</option>
          <option v-for="y in graduationYears" :key="y" :value="y">{{ y }}</option>
        </select>
      </label>

      <label>
        <span>Turma <em>*</em></span>
        <select v-model="klass" class="input" required>
          <option value="" disabled>Selecione</option>
          <option v-for="c in classes" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="button" type="submit" :disabled="!canSubmit">
        {{ saving ? "Salvando…" : "Continuar" }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.onboarding {
  max-width: 480px;
  margin: 2rem auto;
}
.kicker {
  display: inline-block;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.85rem;
}
.onboarding h1 { font-size: 1.8rem; margin: 0 0 0.4rem; }
.onboarding p { color: var(--muted-on-dark); margin: 0 0 1.5rem; }

.form { display: flex; flex-direction: column; gap: 0.85rem; }
.form label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: var(--muted-on-dark);
  font-size: 0.9rem;
}
.form em { color: var(--marista-yellow); font-style: normal; }
.error { color: var(--marista-yellow); font-weight: 600; margin: 0; }
.button { margin-top: 0.4rem; }
</style>
