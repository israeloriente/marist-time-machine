<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  publicStats,
  randomPhotos,
  type PublicStats,
  type RandomPhoto,
} from "@/services/api";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();

const mosaicPhotos = ref<RandomPhoto[]>([]);
const stats = ref<PublicStats | null>(null);

const fmt = new Intl.NumberFormat("pt-BR");

onMounted(async () => {
  // Both endpoints are public — no need to wait for auth.
  const [photos, s] = await Promise.all([
    randomPhotos(24).catch(() => []),
    publicStats().catch(() => null),
  ]);
  mosaicPhotos.value = photos;
  stats.value = s;
});
</script>

<template>
  <!-- Hero with photo mosaic background -->
  <section class="home-hero">
    <div class="mosaic" aria-hidden="true">
      <div
        v-for="(p, i) in mosaicPhotos"
        :key="p.id"
        class="mosaic-tile"
        :style="{ backgroundImage: `url(${p.thumb_signed_url || p.signed_url})`, animationDelay: `${(i % 8) * 0.4}s` }"
      />
    </div>
    <div class="hero-overlay" />

    <div class="hero-content">
      <span class="kicker">Acervo Marista Pio X</span>
      <h1 class="hero-title">
        Volte no tempo.<br />
        <span class="accent">Encontre você nas fotos.</span>
      </h1>
      <p class="hero-lead">
        Tire uma selfie e a gente acha todas as fotos do colégio onde você
        aparece — em segundos.
      </p>

      <div class="cta-row">
        <RouterLink
          v-if="auth.session"
          to="/capture"
          class="button cta-primary"
        >
          📸 Buscar com selfie
        </RouterLink>
        <RouterLink
          v-if="auth.session"
          to="/upload"
          class="button cta-secondary"
        >
          + Adicionar fotos
        </RouterLink>
        <RouterLink v-else to="/login" class="button cta-primary">
          Entrar para começar →
        </RouterLink>
      </div>
    </div>
  </section>

  <!-- Acervo stats — show real numbers when we have them -->
  <section v-if="stats && stats.photos > 0" class="stats">
    <div class="stat">
      <strong class="stat-num">{{ fmt.format(stats.photos) }}</strong>
      <span class="stat-label">fotos no acervo</span>
    </div>
    <div class="stat">
      <strong class="stat-num">{{ fmt.format(stats.named_people) }}</strong>
      <span class="stat-label">pessoas identificadas</span>
    </div>
    <div class="stat">
      <strong class="stat-num">{{ stats.years }}</strong>
      <span class="stat-label">{{ stats.years === 1 ? "turma" : "turmas" }}</span>
    </div>
    <div v-if="stats.oldest_year" class="stat">
      <strong class="stat-num">desde {{ stats.oldest_year }}</strong>
      <span class="stat-label">do colégio</span>
    </div>
  </section>

  <!-- Action grid -->
  <section v-if="auth.session" class="actions">
    <h2 class="section-title">O que você quer fazer?</h2>
    <div class="action-grid">
      <RouterLink to="/capture" class="action-card primary">
        <span class="action-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </span>
        <strong>Buscar</strong>
        <span class="action-desc">Tire uma selfie e ache suas fotos.</span>
      </RouterLink>

      <RouterLink to="/upload" class="action-card">
        <span class="action-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 13V3" />
            <path d="m7 8 5-5 5 5" />
            <path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6" />
          </svg>
        </span>
        <strong>Adicionar fotos</strong>
        <span class="action-desc">Suba fotos e vídeos do colégio.</span>
      </RouterLink>

      <RouterLink to="/contribute" class="action-card">
        <span class="action-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M4 21v-2a4 4 0 0 1 3-3.87" />
            <circle cx="12" cy="7" r="4" />
            <path d="m9 17 2 2 4-4" />
          </svg>
        </span>
        <strong>Identificar pessoas</strong>
        <span class="action-desc">Reconheceu alguém? Sugira o nome.</span>
      </RouterLink>

      <RouterLink to="/musicas" class="action-card">
        <span class="action-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 18V5l12-2v13" />
            <circle cx="6" cy="18" r="3" />
            <circle cx="18" cy="16" r="3" />
          </svg>
        </span>
        <strong>Trilha sonora</strong>
        <span class="action-desc">Músicas do toque que marcaram a sua vida.</span>
      </RouterLink>

      <RouterLink to="/kiosk" class="action-card">
        <span class="action-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" />
            <path d="M8 21h8" />
            <path d="M12 17v4" />
          </svg>
        </span>
        <strong>Apresentação do mural</strong>
        <span class="action-desc">Veja o modo de exibição em tela cheia.</span>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
/* ========= HERO ========= */
.home-hero {
  position: relative;
  margin: -1rem -1rem 1.5rem;
  padding: 4.5rem 1.25rem 5rem;
  overflow: hidden;
  background: linear-gradient(135deg, #0c2c4f 0%, #0a1f3a 100%);
  border-bottom: 4px solid var(--marista-yellow);
}

/* Mosaic */
.mosaic {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  grid-auto-rows: 1fr;
  gap: 4px;
  opacity: 0.32;
  pointer-events: none;
  filter: blur(1px) saturate(1.1);
}
.mosaic-tile {
  background-size: cover;
  background-position: center;
  border-radius: 6px;
  animation: tile-pulse 8s ease-in-out infinite;
  min-height: 80px;
}
@keyframes tile-pulse {
  0%, 100% { opacity: 0.85; transform: scale(1); }
  50%      { opacity: 1; transform: scale(1.04); }
}
/* Gradient over the mosaic to keep text legible */
.hero-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 25% 30%, rgba(12, 44, 79, 0.55) 0%, rgba(12, 44, 79, 0.92) 70%),
    linear-gradient(180deg, rgba(12, 44, 79, 0.55) 0%, rgba(10, 31, 58, 0.95) 100%);
  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 2;
  max-width: 720px;
  margin: 0 auto;
}
.kicker {
  display: inline-block;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  border-radius: 999px;
  padding: 0.35rem 0.95rem;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 1rem;
}
.hero-title {
  color: var(--marista-white);
  font-size: clamp(2rem, 7vw, 3.5rem);
  margin: 0 0 1rem;
  line-height: 1.05;
  font-weight: 800;
  letter-spacing: -0.02em;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.45);
}
.hero-title .accent {
  color: var(--marista-yellow);
}
.hero-lead {
  color: rgba(255, 255, 255, 0.88);
  font-size: clamp(1rem, 2.5vw, 1.2rem);
  margin: 0 0 1.6rem;
  max-width: 560px;
  line-height: 1.5;
}

.cta-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.cta-primary {
  background: var(--marista-yellow);
  color: var(--marista-navy);
  border: none;
  font-weight: 800;
  font-size: 1rem;
  padding: 0.95rem 1.5rem;
  border-radius: 999px;
  box-shadow: 0 8px 24px rgba(247, 201, 72, 0.35);
  transition: transform 0.1s, box-shadow 0.15s;
}
.cta-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 32px rgba(247, 201, 72, 0.5);
}
.cta-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: var(--marista-white);
  border: 1px solid rgba(255, 255, 255, 0.35);
  font-weight: 600;
  padding: 0.85rem 1.4rem;
  border-radius: 999px;
}
.cta-secondary:hover {
  background: rgba(255, 255, 255, 0.18);
}

/* ========= STATS ========= */
.stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.6rem;
  margin: 0 0 1.75rem;
}
.stat {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.9rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.stat-num {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--marista-navy);
  line-height: 1;
  letter-spacing: -0.01em;
}
.stat-label {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 500;
}

/* ========= ACTION GRID ========= */
.section-title {
  margin: 0 0 0.85rem;
  font-size: 1.05rem;
  color: var(--marista-navy);
  font-weight: 700;
}
.action-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.7rem;
}
.action-card {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto;
  column-gap: 0.85rem;
  row-gap: 0.2rem;
  align-items: center;
  padding: 1rem 1.1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  text-decoration: none;
  color: var(--text);
  transition: border-color 0.15s, transform 0.05s, box-shadow 0.15s;
}
.action-card:hover {
  border-color: var(--marista-blue);
  box-shadow: 0 6px 18px rgba(14, 109, 194, 0.1);
}
.action-card:active { transform: scale(0.99); }
.action-card.primary {
  background: linear-gradient(135deg, rgba(14, 109, 194, 0.08), rgba(247, 201, 72, 0.08));
  border-color: rgba(14, 109, 194, 0.3);
}
.action-icon {
  grid-row: 1 / span 2;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(14, 109, 194, 0.12);
  color: var(--marista-blue);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.action-card.primary .action-icon {
  background: var(--marista-yellow);
  color: var(--marista-navy);
}
.action-icon svg { width: 22px; height: 22px; }
.action-card strong {
  font-size: 1rem;
  color: var(--marista-navy);
}
.action-desc {
  font-size: 0.85rem;
  color: var(--muted);
  grid-column: 2;
}

/* ========= RESPONSIVE ========= */
@media (min-width: 640px) {
  .home-hero {
    margin: -1.5rem -1.5rem 2rem;
    padding: 5.5rem 2rem 6rem;
  }
  .mosaic { grid-template-columns: repeat(8, 1fr); }
  .stats {
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
  }
  .stat { padding: 1rem 1.2rem; }
  .stat-num { font-size: 1.7rem; }
  .action-grid {
    grid-template-columns: 1fr 1fr;
    gap: 0.85rem;
  }
}
@media (min-width: 900px) {
  .action-grid { grid-template-columns: repeat(5, 1fr); }
  .action-card {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    text-align: center;
    justify-items: center;
    padding: 1.4rem 1rem 1.2rem;
  }
  .action-icon {
    grid-row: 1;
    width: 56px;
    height: 56px;
  }
  .action-icon svg { width: 28px; height: 28px; }
  .action-desc { grid-column: 1; }
}
</style>
