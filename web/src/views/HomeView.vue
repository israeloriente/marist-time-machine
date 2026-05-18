<script setup lang="ts">
import { RouterLink } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
</script>

<template>
  <section class="hero home-hero">
    <div class="home-hero-content">
      <span class="kicker">Acervo Marista Pio X</span>
      <h1>Volte no tempo.</h1>
      <p>
        Tire uma selfie e a gente encontra todas as suas fotos no acervo da escola.
      </p>
      <div class="cta-row">
        <RouterLink v-if="auth.session" to="/capture" class="button">Buscar agora</RouterLink>
        <RouterLink v-if="auth.session" to="/upload" class="button secondary on-blue">
          Adicionar fotos
        </RouterLink>
        <RouterLink v-else to="/login" class="button">Entrar para buscar</RouterLink>
      </div>
    </div>
    <svg class="home-blob" viewBox="0 0 200 200" aria-hidden="true">
      <path
        d="M48,-58C61,-46,69,-29,71,-12C73,5,69,22,59,36C49,49,33,58,15,64C-3,69,-22,72,-39,65C-56,57,-71,40,-76,21C-81,2,-76,-19,-65,-34C-54,-49,-37,-57,-21,-63C-5,-69,11,-72,25,-71C39,-70,52,-65,48,-58Z"
        transform="translate(100 100)"
        fill="#5cbdf7"
        opacity="0.35"
      />
    </svg>
  </section>

  <div v-if="auth.session" class="features">
    <RouterLink to="/contribute" class="feature-card">
      <div class="feature-icon">💡</div>
      <strong>Identificar pessoas</strong>
      <span class="muted small">
        Reconheceu alguém? Sugira o nome. Sua sugestão passa por revisão.
      </span>
    </RouterLink>
    <RouterLink to="/upload" class="feature-card">
      <div class="feature-icon">📷</div>
      <strong>Adicionar ao acervo</strong>
      <span class="muted small">
        Suba fotos ou vídeos. A gente cuida do reconhecimento facial.
      </span>
    </RouterLink>
  </div>
</template>

<style scoped>
.home-hero {
  display: grid;
  grid-template-columns: 1fr;
  margin-bottom: 1.25rem;
  position: relative;
  overflow: hidden;
}
.home-hero-content {
  position: relative;
  z-index: 1;
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
.home-hero h1 {
  color: var(--text-on-dark);
  font-size: 2rem;
  margin: 0 0 0.6rem;
  line-height: 1.1;
}
.home-hero p {
  color: var(--muted-on-dark);
  margin: 0 0 1.25rem;
  max-width: 480px;
}
.cta-row {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.button.secondary.on-blue {
  background: transparent;
  color: var(--marista-white);
  border-color: rgba(255, 255, 255, 0.5);
}
.button.secondary.on-blue:hover {
  background: rgba(255, 255, 255, 0.1);
}
.home-blob {
  position: absolute;
  right: -40px;
  top: -40px;
  width: 280px;
  height: 280px;
  pointer-events: none;
}

.features {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
}
.feature-card {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.15s, transform 0.05s;
}
.feature-card:hover {
  border-color: var(--marista-blue);
}
.feature-card:active {
  transform: scale(0.99);
}
.feature-icon {
  font-size: 1.6rem;
  line-height: 1;
}
.feature-card strong { color: var(--marista-navy); }

@media (min-width: 640px) {
  .home-hero { padding: 2.25rem; }
  .home-hero h1 { font-size: 2.5rem; }
  .features { grid-template-columns: 1fr 1fr; }
}
</style>
