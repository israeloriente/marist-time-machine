<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import MediaPreview from "@/components/MediaPreview.vue";
import ReportDialog from "@/components/ReportDialog.vue";
import { useResultsStore } from "@/stores/results";

const results = useResultsStore();

// ----- Lightbox -----
const lightboxIdx = ref<number | null>(null);
const currentPhoto = computed(() => {
  if (lightboxIdx.value === null || !results.data) return null;
  return results.data.photos[lightboxIdx.value] ?? null;
});

function openLightbox(idx: number) {
  lightboxIdx.value = idx;
}
function closeLightbox() {
  lightboxIdx.value = null;
}

function onKey(e: KeyboardEvent) {
  if (lightboxIdx.value === null || !results.data) return;
  const total = results.data.photos.length;
  if (e.key === "Escape") closeLightbox();
  else if (e.key === "ArrowRight" && lightboxIdx.value < total - 1)
    lightboxIdx.value++;
  else if (e.key === "ArrowLeft" && lightboxIdx.value > 0) lightboxIdx.value--;
}

watch(
  () => lightboxIdx.value !== null,
  (open) => {
    if (open) window.addEventListener("keydown", onKey);
    else window.removeEventListener("keydown", onKey);
  },
);
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));

// ----- Report -----
const reportOpen = ref(false);
const reportTarget = ref<{ photo_id: string; thumb_url: string } | null>(null);

function openReport() {
  if (!currentPhoto.value) return;
  reportTarget.value = {
    photo_id: currentPhoto.value.photo_id,
    thumb_url: currentPhoto.value.thumb_signed_url || currentPhoto.value.signed_url,
  };
  reportOpen.value = true;
}
</script>

<template>
  <section class="card">
    <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 1rem">
      <h2>Resultados</h2>
      <RouterLink to="/capture" class="muted">Tentar de novo</RouterLink>
    </div>

    <p v-if="!results.data" class="muted">Nenhuma busca feita ainda.</p>
    <template v-else>
      <p class="muted">
        {{ results.data.photos.length }} fotos encontradas
        <template v-if="results.data.person_id">
          — pessoa identificada
        </template>
      </p>

      <div v-if="!results.data.photos.length" class="muted" style="margin-top: 1rem">
        Não achamos correspondências na base. Tente outra foto com melhor iluminação.
      </div>

      <div class="grid" style="margin-top: 1rem">
        <button
          v-for="(p, idx) in results.data.photos"
          :key="p.photo_id"
          type="button"
          class="result-tile"
          :title="`distância ${p.distance.toFixed(3)}`"
          @click="openLightbox(idx)"
        >
          <MediaPreview
            :src="p.signed_url"
            :thumb-src="p.thumb_signed_url"
            :media-type="p.media_type"
            :alt="`Mídia ${p.photo_id}`"
          />
        </button>
      </div>
    </template>
  </section>

  <!-- Lightbox in-app com botão de denúncia -->
  <Transition name="fade">
    <div
      v-if="lightboxIdx !== null && currentPhoto"
      class="lightbox"
      role="dialog"
      aria-modal="true"
      @click.self="closeLightbox"
    >
      <button class="lightbox-close" aria-label="Fechar" @click="closeLightbox">×</button>

      <button
        v-if="lightboxIdx > 0"
        class="lightbox-nav prev"
        aria-label="Anterior"
        @click="lightboxIdx = (lightboxIdx ?? 0) - 1"
      >‹</button>
      <button
        v-if="results.data && lightboxIdx < results.data.photos.length - 1"
        class="lightbox-nav next"
        aria-label="Próxima"
        @click="lightboxIdx = (lightboxIdx ?? 0) + 1"
      >›</button>

      <div class="lightbox-media">
        <video
          v-if="currentPhoto.media_type === 'video'"
          :src="currentPhoto.signed_url"
          controls
          autoplay
          playsinline
        />
        <img
          v-else
          :src="currentPhoto.signed_url"
          alt=""
        />
      </div>

      <button
        class="lightbox-report"
        type="button"
        aria-label="Denunciar esta mídia"
        @click="openReport"
      >🚩 Denunciar</button>

      <p v-if="results.data" class="lightbox-counter">
        {{ lightboxIdx + 1 }} / {{ results.data.photos.length }}
      </p>
    </div>
  </Transition>

  <ReportDialog
    :open="reportOpen"
    :photo-id="reportTarget?.photo_id"
    :thumb-url="reportTarget?.thumb_url"
    @close="reportOpen = false"
  />
</template>

<style scoped>
.result-tile {
  display: block;
  aspect-ratio: 1 / 1;
  border-radius: 10px;
  overflow: hidden;
  background: var(--surface-strong);
  border: 1px solid var(--border);
  padding: 0;
  cursor: pointer;
  font: inherit;
  color: inherit;
  transition: transform 0.1s, border-color 0.15s;
}
.result-tile:hover {
  transform: scale(1.02);
  border-color: var(--marista-blue);
}

/* ----- Lightbox ----- */
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(0, 0, 0, 0.92);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4vh 4vw;
}
.lightbox-media {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.lightbox-media img,
.lightbox-media video {
  max-width: 100%;
  max-height: 100%;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.lightbox-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  cursor: pointer;
  font-size: 1.5rem;
  font-weight: 300;
  z-index: 60;
  transition: background 0.15s;
}
.lightbox-close:hover { background: rgba(255, 255, 255, 0.2); }

.lightbox-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  cursor: pointer;
  font-size: 2.2rem;
  font-weight: 300;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  padding-bottom: 4px;
  transition: background 0.15s;
}
.lightbox-nav:hover { background: rgba(255, 255, 255, 0.2); }
.lightbox-nav.prev { left: 1rem; }
.lightbox-nav.next { right: 1rem; }

.lightbox-report {
  position: absolute;
  top: 1rem;
  left: 1rem;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.95rem;
  border-radius: 999px;
  background: rgba(214, 58, 58, 0.7);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.25);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  z-index: 60;
  transition: background 0.15s;
}
.lightbox-report:hover { background: rgba(214, 58, 58, 0.9); }

.lightbox-counter {
  position: absolute;
  bottom: 1.2rem;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.6);
  color: var(--marista-yellow);
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.9rem;
  letter-spacing: 0.04em;
  margin: 0;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
