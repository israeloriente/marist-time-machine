<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { useProfileStore } from "@/stores/profile";

const authStore = useAuthStore();
const profileStore = useProfileStore();

const currentYear = new Date().getFullYear();
const graduationYears = Array.from({ length: 111 }, (_, i) => currentYear + 10 - i);
const classes = ["A", "B", "C", "D", "E", "F"];

const year = ref<number | "">("");
const klass = ref<string>("");
const saving = ref(false);
const saved = ref(false);
const error = ref<string | null>(null);

const userEmail = computed(() => authStore.session?.user?.email ?? "");

const canSubmit = computed(() => year.value !== "" && klass.value !== "" && !saving.value);

async function submit() {
  saving.value = true;
  error.value = null;
  saved.value = false;
  try {
    await profileStore.save(year.value as number, klass.value);
    saved.value = true;
    setTimeout(() => (saved.value = false), 2500);
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? e.message ?? String(e);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await profileStore.load();
  if (profileStore.profile) {
    year.value = profileStore.profile.graduation_year;
    klass.value = profileStore.profile.class_letter;
  }
});
</script>

<template>
  <section class="card profile-card">
    <h2>Meu perfil</h2>
    <p class="muted">Atualize seus dados a qualquer momento.</p>

    <dl class="email-line">
      <dt>Email</dt>
      <dd>{{ userEmail }}</dd>
    </dl>

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
      <p v-if="saved" class="success">✓ Salvo</p>

      <div class="actions">
        <button class="button" type="submit" :disabled="!canSubmit">
          {{ saving ? "Salvando…" : "Salvar" }}
        </button>
        <button class="button secondary" type="button" @click="authStore.signOut">
          Sair da conta
        </button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.profile-card { max-width: 520px; margin: 0 auto; }

.email-line {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.4rem 1rem;
  margin: 1rem 0;
  padding: 0.6rem 0.9rem;
  background: var(--surface-strong);
  border-radius: 8px;
}
.email-line dt { color: var(--muted); font-size: 0.85rem; }
.email-line dd { margin: 0; font-weight: 600; }

.form { display: flex; flex-direction: column; gap: 0.85rem; }
.form label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: var(--muted);
  font-size: 0.9rem;
}
.form em { color: var(--marista-yellow); font-style: normal; }

.actions { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.4rem; }
.success { color: #4ade80; font-weight: 600; margin: 0; }
</style>
