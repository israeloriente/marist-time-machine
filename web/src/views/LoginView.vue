<script setup lang="ts">
import { useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();

async function signIn() {
  // After Google redirects back, Supabase finishes the session and we
  // land the user where they originally wanted to go.
  const redirect = (route.query.redirect as string) || "/";
  await auth.signInWithGoogle(redirect);
}
</script>

<template>
  <section class="login-card">
    <span class="kicker">Acervo Marista Pio X</span>
    <h1>Bem-vindo de volta</h1>
    <p class="lead">
      Entre com sua conta Google pra acessar suas fotos do colégio.
    </p>

    <button
      type="button"
      class="google-btn"
      :disabled="auth.loading"
      @click="signIn"
    >
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        />
        <path
          fill="#34A853"
          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        />
        <path
          fill="#FBBC05"
          d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.61z"
        />
        <path
          fill="#EA4335"
          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"
        />
      </svg>
      <span>{{ auth.loading ? "Redirecionando…" : "Entrar com Google" }}</span>
    </button>

    <p v-if="auth.error" class="error">{{ auth.error }}</p>

    <p class="legal muted">
      Ao entrar você concorda em ter sua foto usada apenas pra te ajudar a
      reencontrar memórias do colégio. Você pode pedir a remoção a qualquer
      momento.
    </p>
  </section>
</template>

<style scoped>
.login-card {
  max-width: 440px;
  margin: 3rem auto;
  padding: 2rem 1.5rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(12, 44, 79, 0.08);
  text-align: center;
}
.kicker {
  display: inline-block;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font-size: 0.7rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 1rem;
}
.login-card h1 {
  margin: 0 0 0.5rem;
  font-size: 1.6rem;
  color: var(--marista-navy);
}
.lead {
  margin: 0 0 1.75rem;
  color: var(--muted);
  line-height: 1.5;
}

.google-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.7rem;
  width: 100%;
  padding: 0.9rem 1.25rem;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.05s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.google-btn:hover:not(:disabled) {
  border-color: var(--marista-blue);
  box-shadow: 0 4px 12px rgba(14, 109, 194, 0.15);
}
.google-btn:active:not(:disabled) { transform: scale(0.99); }
.google-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  margin: 1rem 0 0;
  padding: 0.65rem 0.85rem;
  background: rgba(214, 58, 58, 0.08);
  border: 1px solid rgba(214, 58, 58, 0.3);
  color: var(--error);
  border-radius: 8px;
  font-size: 0.88rem;
}

.legal {
  margin: 1.75rem 0 0;
  font-size: 0.78rem;
  line-height: 1.5;
}
</style>
