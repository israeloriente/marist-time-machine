<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  randomPhotos,
  searchByFace,
  songsApi,
  type RandomPhoto,
  type SearchResponse,
  type Song,
} from "@/services/api";

type Phase =
  | "idle"
  | "loading-camera"
  | "ready"
  | "running"
  | "reveal"
  | "results"
  | "year-photos";

const phase = ref<Phase>("idle");
const error = ref<string | null>(null);

// Reveal phase: drip photos one at a time
const revealIdx = ref(0);
let revealTimer: number | null = null;
const PHOTO_REVEAL_MS = 4000;       // hold each photo this long AFTER it loads
const MAX_DECODE_WAIT_MS = 10_000;  // skip an image if it can't decode in 10s
const MAX_REVEAL_PHOTOS = 12;       // cap reveal duration; rest goes to grid

// Cache of fully-decoded images keyed by photo_id. When the <img> in the
// DOM gets the same src, it paints synchronously from this cache instead
// of going through another load+decode cycle.
const decodedCache = new Map<string, HTMLImageElement>();
const decodingPromises = new Map<string, Promise<boolean>>();

const currentYear = new Date().getFullYear();
const years = Array.from({ length: 60 }, (_, i) => currentYear - i);
const selectedYear = ref<number>(currentYear - 10);

// Hidden camera elements
const videoEl = ref<HTMLVideoElement | null>(null);
const stream = ref<MediaStream | null>(null);

// Slideshow
const photos = ref<RandomPhoto[]>([]);
const slideIdx = ref(0);
let slideTimer: number | null = null;

// Hidden YouTube player
const playerEl = ref<HTMLDivElement | null>(null);
let ytPlayer: any = null;
let ytReadyPromise: Promise<void> | null = null;
const songs = ref<Song[]>([]);
const currentSongIdx = ref(0);
const currentSongTitle = ref<string>("");

// Search result
const result = ref<SearchResponse | null>(null);
const totalSteps = 4; // pseudo progress
const progressStep = ref(0);

// Lightbox (in-app modal for the results grid)
// source: 'match' = personal matches, 'year' = full graduation-year roll
type LightboxSource = "match" | "year";
const lightboxIdx = ref<number | null>(null);
const lightboxSource = ref<LightboxSource>("match");
function openLightbox(idx: number, source: LightboxSource = "match") {
  lightboxSource.value = source;
  lightboxIdx.value = idx;
}
function closeLightbox() {
  lightboxIdx.value = null;
}

const lightboxList = computed(() => {
  if (lightboxSource.value === "year") {
    return yearPhotos.value.map((p) => ({
      signed_url: p.signed_url,
      thumb_signed_url: p.thumb_signed_url,
      media_type: "image" as const,
    }));
  }
  return (result.value?.photos ?? []).map((p) => ({
    signed_url: p.signed_url,
    thumb_signed_url: p.thumb_signed_url,
    media_type: p.media_type,
  }));
});

// Year photos (full graduation-year roll, shown after personal matches)
const yearPhotos = ref<RandomPhoto[]>([]);
const yearPhotosLoading = ref(false);

async function showYearPhotos() {
  phase.value = "year-photos";
  if (yearPhotos.value.length) return; // already loaded
  yearPhotosLoading.value = true;
  try {
    yearPhotos.value = await randomPhotos(120, selectedYear.value);
  } catch (e) {
    console.error("year photos failed", e);
    yearPhotos.value = [];
  } finally {
    yearPhotosLoading.value = false;
  }
}

function backToResults() {
  phase.value = "results";
}

// Keyboard navigation for the lightbox
function onLightboxKey(e: KeyboardEvent) {
  if (lightboxIdx.value === null) return;
  const total = lightboxList.value.length;
  if (e.key === "Escape") {
    closeLightbox();
  } else if (e.key === "ArrowRight" && lightboxIdx.value < total - 1) {
    lightboxIdx.value++;
  } else if (e.key === "ArrowLeft" && lightboxIdx.value > 0) {
    lightboxIdx.value--;
  }
}

const SEARCH_DURATION_MS = 8000; // animação dura ~8s antes de mostrar resultado

// ---- Lifecycle ----
// Kiosk page is public — no auth required. The 3 endpoints it calls
// (/search, /photos/random, /songs/random) accept anonymous requests.

async function startCamera() {
  phase.value = "loading-camera";
  error.value = null;

  // Make absolutely sure no leftover stream is holding the camera. Some
  // iOS/Android browsers return "Timeout starting video source" when a
  // previous track is still in "live" state when getUserMedia is called
  // again.
  stopCamera();
  if (videoEl.value) {
    try {
      videoEl.value.pause();
    } catch { /* ignore */ }
    videoEl.value.srcObject = null;
  }
  // Brief wait gives the underlying driver time to release the device.
  await new Promise((r) => setTimeout(r, 200));

  // Try progressively more permissive constraints. The kiosk doesn't need
  // 1280x720 — InsightFace happily works with whatever the camera offers.
  const attempts: MediaStreamConstraints[] = [
    { video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
    { video: { facingMode: "user" }, audio: false },
    { video: true, audio: false },
  ];

  let lastErr: any = null;
  for (let i = 0; i < attempts.length; i++) {
    try {
      stream.value = await navigator.mediaDevices.getUserMedia(attempts[i]);
      break;
    } catch (e: any) {
      lastErr = e;
      // small back-off between attempts to let the driver settle
      await new Promise((r) => setTimeout(r, 300));
    }
  }

  if (!stream.value) {
    error.value =
      "Não foi possível acessar a câmera: " +
      (lastErr?.message ?? String(lastErr)) +
      ". Tente sair e voltar a essa página, ou recarregue.";
    phase.value = "idle";
    return;
  }

  try {
    if (videoEl.value) {
      videoEl.value.srcObject = stream.value;
      // play() can throw NotAllowedError on iOS if the gesture chain broke;
      // we don't care because the user already clicked the CTA.
      await videoEl.value.play().catch(() => undefined);
    }
    phase.value = "ready";
  } catch (e: any) {
    error.value = "Erro ao iniciar vídeo: " + (e.message ?? e);
    stopCamera();
    phase.value = "idle";
  }
}

function stopCamera() {
  if (stream.value) {
    stream.value.getTracks().forEach((t) => {
      try { t.stop(); } catch { /* ignore */ }
    });
    stream.value = null;
  }
  if (videoEl.value && videoEl.value.srcObject) {
    videoEl.value.srcObject = null;
  }
}

async function captureSnapshot(): Promise<Blob | null> {
  if (!videoEl.value) return null;
  const v = videoEl.value;
  if (!v.videoWidth) return null;
  const canvas = document.createElement("canvas");
  canvas.width = v.videoWidth;
  canvas.height = v.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(v, 0, 0);
  return await new Promise((res) => canvas.toBlob((b) => res(b), "image/jpeg", 0.92));
}

// ---- YouTube IFrame API (hidden player for audio) ----

function loadYouTubeAPI(): Promise<void> {
  if (ytReadyPromise) return ytReadyPromise;
  ytReadyPromise = new Promise((resolve) => {
    if ((window as any).YT && (window as any).YT.Player) {
      resolve();
      return;
    }
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
    (window as any).onYouTubeIframeAPIReady = () => resolve();
  });
  return ytReadyPromise;
}

async function playNextSong() {
  if (!songs.value.length) return;
  const s = songs.value[currentSongIdx.value % songs.value.length];
  currentSongTitle.value = s.title || "♪";
  currentSongIdx.value++;

  await loadYouTubeAPI();
  if (!playerEl.value) return;

  if (!ytPlayer) {
    ytPlayer = new (window as any).YT.Player(playerEl.value, {
      height: "1",
      width: "1",
      videoId: s.youtube_id,
      playerVars: { autoplay: 1, controls: 0, modestbranding: 1, playsinline: 1 },
      events: {
        onReady: (e: any) => {
          e.target.setVolume(70);
          e.target.playVideo();
        },
        onStateChange: (e: any) => {
          // 0 = ended → próxima
          if (e.data === 0) playNextSong();
        },
        onError: () => playNextSong(),
      },
    });
  } else {
    ytPlayer.loadVideoById(s.youtube_id);
  }
}

function stopMusic() {
  try {
    ytPlayer?.stopVideo?.();
    ytPlayer?.destroy?.();
  } catch {
    /* ignore */
  }
  ytPlayer = null;
}

// ---- Main flow ----

async function startJourney() {
  // Make sure camera is ready (no-op if already running)
  if (!stream.value) {
    await startCamera();
  }
  if (!stream.value) return; // startCamera failed → error already set

  phase.value = "running";
  progressStep.value = 0;
  result.value = null;

  // 1) Fetch slideshow + songs in parallel (start animation ASAP)
  const photosP = randomPhotos(40, selectedYear.value).catch(() => []);
  const songsP = songsApi.random(selectedYear.value, 20).catch(() => []);

  photos.value = await photosP;
  songs.value = await songsP;

  startSlideshow();
  if (songs.value.length) playNextSong();

  // 2) Capture the user discreetly during the 1st second of animation,
  //    after a brief settle so the camera autoexposure stabilizes.
  await new Promise((r) => setTimeout(r, 1200));
  const snap = await captureSnapshot();
  progressStep.value = 1;

  // 3) Send to /search in background while animation continues.
  let searchP: Promise<SearchResponse> | null = null;
  if (snap) {
    searchP = searchByFace(snap).catch((e) => {
      console.error("search failed", e);
      return { person_id: null, matched_faces: 0, photos: [] } as SearchResponse;
    });
  }

  // Animated progress bar — purely visual
  const stepEvery = SEARCH_DURATION_MS / totalSteps;
  for (let i = 1; i < totalSteps; i++) {
    await new Promise((r) => setTimeout(r, stepEvery));
    progressStep.value = i + 1;
  }

  // 4) Make sure the search is done before transitioning.
  const res = searchP ? await searchP : ({ person_id: null, matched_faces: 0, photos: [] } as SearchResponse);
  result.value = res;

  // 5) Preload every reveal photo in parallel BEFORE the reveal starts —
  //    music keeps playing so the user feels the moment building up. We
  //    cap the wait so a single slow URL doesn't keep them staring at the
  //    slideshow forever.
  if (res.photos.length) {
    await preloadAllRevealPhotos(res.photos.slice(0, MAX_REVEAL_PHOTOS));
  }

  // Stop the ambient slideshow and camera; music keeps playing.
  stopCamera();
  stopSlideshow();

  // If we found photos, drip them one by one (dramatic reveal).
  // If we found none, go straight to the "no results" screen.
  if (res.photos.length) {
    startReveal();
  } else {
    phase.value = "results";
  }
}

const PRELOAD_MAX_WAIT_MS = 8000;

interface PreloadablePhoto {
  photo_id: string;
  signed_url: string;
  thumb_signed_url?: string | null;
}

function pickUrl(p: PreloadablePhoto): string {
  return p.thumb_signed_url || p.signed_url;
}

/**
 * Decode an image fully (pixels ready to paint) and stash it in the cache.
 * Returns true on success, false on error. Idempotent: concurrent calls
 * for the same id share a single in-flight promise.
 */
function decodeOne(p: PreloadablePhoto): Promise<boolean> {
  const existing = decodingPromises.get(p.photo_id);
  if (existing) return existing;
  if (decodedCache.has(p.photo_id)) return Promise.resolve(true);

  const url = pickUrl(p);
  const img = new Image();
  // Hint the browser to decode off the main thread.
  img.decoding = "async";
  img.src = url;

  const promise = (async () => {
    try {
      // HTMLImageElement.decode() resolves only when the image is fully
      // decoded and ready to paint — much stronger guarantee than `load`.
      await img.decode();
      decodedCache.set(p.photo_id, img);
      return true;
    } catch {
      return false;
    } finally {
      decodingPromises.delete(p.photo_id);
    }
  })();

  decodingPromises.set(p.photo_id, promise);
  return promise;
}

function preloadAllRevealPhotos(items: PreloadablePhoto[]): Promise<void> {
  // Kick off every decode in parallel; resolve when all settle OR the
  // overall budget elapses. The decodes keep going in the background
  // either way — anything that misses the budget will likely be ready
  // by the time the reveal walks to it.
  const all = Promise.allSettled(items.map(decodeOne)).then(() => undefined);
  const timeout = new Promise<void>((r) => setTimeout(r, PRELOAD_MAX_WAIT_MS));
  return Promise.race([all, timeout]);
}

/** Wait up to `timeoutMs` for the photo to decode. Returns true if it did. */
function waitForDecode(p: PreloadablePhoto, timeoutMs: number): Promise<boolean> {
  if (decodedCache.has(p.photo_id)) return Promise.resolve(true);
  return new Promise<boolean>((resolve) => {
    let settled = false;
    const timer = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      resolve(false);
    }, timeoutMs);
    decodeOne(p).then((ok) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      resolve(ok);
    });
  });
}

function totalReveal(): number {
  return Math.min(result.value?.photos.length ?? 0, MAX_REVEAL_PHOTOS);
}

async function startReveal() {
  // Tear down any prior reveal cleanly
  stopReveal();

  if (totalReveal() === 0) {
    phase.value = "results";
    return;
  }

  // Make sure the FIRST photo is fully decoded before we even enter the
  // reveal phase — this is what kills the "skeleton flashes then jumps to
  // the next" feeling. The preload pass already started this; we just
  // wait for it to finish (with a safety cap).
  const first = result.value?.photos[0];
  if (first) {
    await waitForDecode(first, MAX_DECODE_WAIT_MS);
  }

  phase.value = "reveal";
  revealIdx.value = 0;

  // Prime the lookahead: start decoding photo #1 in parallel with showing #0
  primeLookahead();

  scheduleAdvance(PHOTO_REVEAL_MS);
}

function primeLookahead() {
  // Kick off decode of the next 2 photos so by the time we advance,
  // they're already painted in cache. We do 2 instead of 1 to absorb
  // jitter on slow links.
  for (let lookahead = 1; lookahead <= 2; lookahead++) {
    const p = result.value?.photos[revealIdx.value + lookahead];
    if (p) decodeOne(p);
  }
}

async function advanceReveal() {
  if (phase.value !== "reveal") return;
  const total = totalReveal();
  if (revealIdx.value >= total - 1) {
    phase.value = "results";
    return;
  }

  const nextIdx = revealIdx.value + 1;
  const next = result.value?.photos[nextIdx];
  if (!next) {
    phase.value = "results";
    return;
  }

  // Wait until the next photo is actually decoded before switching to it.
  // If it doesn't decode within budget, skip to the one after that —
  // never sit on a skeleton.
  const ok = await waitForDecode(next, MAX_DECODE_WAIT_MS);
  if (phase.value !== "reveal") return; // user navigated away

  if (!ok) {
    // Skip this photo: bump idx silently and try the next one.
    revealIdx.value = nextIdx;
    primeLookahead();
    advanceReveal();
    return;
  }

  revealIdx.value = nextIdx;
  primeLookahead();
  scheduleAdvance(PHOTO_REVEAL_MS);
}

function scheduleAdvance(delayMs: number) {
  clearAdvanceTimer();
  revealTimer = window.setTimeout(() => {
    revealTimer = null;
    advanceReveal();
  }, delayMs);
}

function clearAdvanceTimer() {
  if (revealTimer !== null) {
    window.clearTimeout(revealTimer);
    revealTimer = null;
  }
}

function skipReveal() {
  stopReveal();
  phase.value = "results";
}

function stopReveal() {
  clearAdvanceTimer();
}

const currentRevealPhoto = computed(() => {
  if (!result.value) return null;
  return result.value.photos[revealIdx.value] || null;
});

// Expose to template
const _maxReveal = MAX_REVEAL_PHOTOS;

function reset() {
  stopMusic();
  stopCamera();
  stopSlideshow();
  stopReveal();
  decodedCache.clear();
  decodingPromises.clear();
  result.value = null;
  photos.value = [];
  yearPhotos.value = [];
  yearPhotosLoading.value = false;
  songs.value = [];
  currentSongIdx.value = 0;
  currentSongTitle.value = "";
  progressStep.value = 0;
  phase.value = "idle";
}

// ---- Slideshow ----

function startSlideshow() {
  slideIdx.value = 0;
  if (slideTimer) window.clearInterval(slideTimer);
  slideTimer = window.setInterval(() => {
    if (photos.value.length) {
      slideIdx.value = (slideIdx.value + 1) % photos.value.length;
    }
  }, 3500);
}
function stopSlideshow() {
  if (slideTimer) {
    window.clearInterval(slideTimer);
    slideTimer = null;
  }
}

const currentPhoto = computed(() => photos.value[slideIdx.value] || null);
const previousPhoto = computed(
  () => photos.value[(slideIdx.value - 1 + photos.value.length) % photos.value.length] || null,
);

const progressPct = computed(() => Math.round((progressStep.value / totalSteps) * 100));

// ---- Init ----

onMounted(() => {
  // Nothing to bootstrap — page is public. Camera prompt happens on user
  // click (browser blocks getUserMedia without a gesture anyway).
  window.addEventListener("keydown", onLightboxKey);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onLightboxKey);
  stopCamera();
  stopMusic();
  stopSlideshow();
  stopReveal();
});
</script>

<template>
  <div class="kiosk" :class="`phase-${phase}`">
    <!-- Hidden camera + YouTube player (kept in DOM even during idle so they
         persist across phases) -->
    <video
      ref="videoEl"
      class="hidden-camera"
      playsinline
      muted
      autoplay
    />
    <div ref="playerEl" class="hidden-player" aria-hidden="true" />

    <!-- IDLE / READY: hero with year picker and CTA -->
    <transition name="fade">
      <section v-if="phase === 'idle' || phase === 'loading-camera' || phase === 'ready'" class="hero">
        <div class="hero-content">
          <span class="kicker">Colégio Marista Pio X</span>
          <h1>Um pedaço de você<br />estará sempre aqui</h1>
          <p class="lead">
            Volte no tempo e reviva momentos do colégio. <br />
            Escolha o ano em que você se formou.
          </p>

          <div class="year-picker">
            <div class="year-track">
              <button
                v-for="y in years"
                :key="y"
                type="button"
                class="year-chip"
                :class="{ active: selectedYear === y }"
                @click="selectedYear = y"
              >{{ y }}</button>
            </div>
          </div>

          <button
            type="button"
            class="big-cta"
            :disabled="phase === 'loading-camera'"
            @click="startJourney"
          >
            <span v-if="phase === 'loading-camera'">Preparando…</span>
            <span v-else>Volte no Tempo</span>
          </button>

          <p v-if="error" class="error">{{ error }}</p>
        </div>

        <div class="hero-bg" aria-hidden="true">
          <div class="orb orb-1" />
          <div class="orb orb-2" />
          <div class="orb orb-3" />
        </div>
      </section>
    </transition>

    <!-- RUNNING: full-screen ken-burns slideshow -->
    <transition name="fade">
      <section v-if="phase === 'running'" class="slideshow">
        <transition-group name="cross" tag="div" class="slide-stack">
          <div
            v-if="currentPhoto"
            :key="currentPhoto.id"
            class="slide-frame ken-burns"
          >
            <div
              class="slide-bg"
              :style="{ backgroundImage: `url(${currentPhoto.signed_url})` }"
            />
            <img :src="currentPhoto.signed_url" class="slide-fg" alt="" />
          </div>
        </transition-group>

        <div class="slide-overlay">
          <div class="search-status">
            <h2>Procurando suas memórias…</h2>
            <p v-if="currentSongTitle" class="now-playing">♪ {{ currentSongTitle }}</p>
            <div class="progress">
              <div class="progress-fill" :style="{ width: progressPct + '%' }" />
            </div>
            <p class="muted">Turma {{ selectedYear }}</p>
          </div>
        </div>
      </section>
    </transition>

    <!-- REVEAL: drip photos one by one full-screen -->
    <transition name="fade">
      <section
        v-if="phase === 'reveal'"
        class="reveal"
        @click="skipReveal"
      >
        <transition-group name="reveal-cross" tag="div" class="reveal-stack">
          <div
            v-if="currentRevealPhoto"
            :key="currentRevealPhoto.photo_id"
            class="reveal-frame ken-burns-slow"
          >
            <div
              class="reveal-bg"
              :style="{
                backgroundImage: `url(${
                  currentRevealPhoto.thumb_signed_url || currentRevealPhoto.signed_url
                })`,
              }"
            />
            <img
              :src="currentRevealPhoto.thumb_signed_url || currentRevealPhoto.signed_url"
              class="reveal-fg is-loaded"
              alt=""
              decoding="sync"
            />
          </div>
        </transition-group>

        <div class="reveal-overlay">
          <div class="reveal-top">
            <span class="kicker">Aqui está você</span>
            <h2 v-if="revealIdx === 0">Encontramos suas memórias</h2>
            <p class="reveal-counter">
              {{ revealIdx + 1 }} de {{ Math.min(result?.photos.length ?? 0, _maxReveal) }}
            </p>
          </div>
          <p class="reveal-hint muted">toque para ver todas →</p>
        </div>
      </section>
    </transition>

    <!-- RESULTS -->
    <transition name="fade">
      <section v-if="phase === 'results'" class="results">
        <div class="results-head">
          <span class="kicker">Aqui está você</span>
          <h2 v-if="result?.photos.length">
            {{ result.photos.length }} {{ result.photos.length === 1 ? "memória encontrada" : "memórias encontradas" }}
          </h2>
          <h2 v-else>Não encontramos suas fotos ainda</h2>
          <p v-if="!result?.photos.length" class="muted">
            Talvez o acervo ainda não tenha você. Mas o reconhecimento aprende — volte em breve.
          </p>
        </div>

        <div v-if="result?.photos.length" class="results-grid">
          <button
            v-for="(p, idx) in result.photos"
            :key="p.photo_id"
            type="button"
            class="result-tile"
            @click="openLightbox(idx, 'match')"
          >
            <img :src="p.thumb_signed_url || p.signed_url" alt="" loading="lazy" />
            <span v-if="p.media_type === 'video'" class="video-pill">▶ vídeo</span>
          </button>
        </div>

        <div class="results-actions">
          <button class="big-cta" type="button" @click="showYearPhotos">
            Ver mais fotos da turma {{ selectedYear }}
          </button>
          <button class="big-cta secondary" type="button" @click="reset">
            Procurar de novo
          </button>
        </div>
      </section>
    </transition>

    <!-- YEAR PHOTOS: full roll of the selected graduation year -->
    <transition name="fade">
      <section v-if="phase === 'year-photos'" class="results">
        <div class="results-head">
          <span class="kicker">Turma {{ selectedYear }}</span>
          <h2>Memórias da turma de {{ selectedYear }}</h2>
          <p class="muted">Todas as fotos do acervo desse ano.</p>
        </div>

        <div v-if="yearPhotosLoading" class="year-loading">
          <div class="skeleton-shimmer" />
          <p class="skeleton-text">Carregando memórias…</p>
        </div>

        <div v-else-if="yearPhotos.length" class="results-grid">
          <button
            v-for="(p, idx) in yearPhotos"
            :key="p.id"
            type="button"
            class="result-tile"
            @click="openLightbox(idx, 'year')"
          >
            <img :src="p.thumb_signed_url || p.signed_url" alt="" loading="lazy" />
          </button>
        </div>

        <p v-else class="muted">Ainda não temos fotos catalogadas dessa turma.</p>

        <div class="results-actions">
          <button class="big-cta secondary" type="button" @click="backToResults">
            ← Voltar às minhas fotos
          </button>
          <button class="big-cta secondary" type="button" @click="reset">
            Procurar de novo
          </button>
        </div>
      </section>
    </transition>

    <!-- LIGHTBOX (in-app modal for full-size view) -->
    <transition name="fade">
      <div
        v-if="lightboxIdx !== null && lightboxList.length"
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
          v-if="lightboxIdx < lightboxList.length - 1"
          class="lightbox-nav next"
          aria-label="Próxima"
          @click="lightboxIdx = (lightboxIdx ?? 0) + 1"
        >›</button>

        <div class="lightbox-media">
          <video
            v-if="lightboxList[lightboxIdx].media_type === 'video'"
            :src="lightboxList[lightboxIdx].signed_url"
            controls
            autoplay
            playsinline
          />
          <img
            v-else
            :src="lightboxList[lightboxIdx].signed_url"
            alt=""
          />
        </div>

        <p class="lightbox-counter">
          {{ lightboxIdx + 1 }} / {{ lightboxList.length }}
        </p>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.kiosk {
  position: fixed;
  inset: 0;
  background: linear-gradient(180deg, #0c2c4f 0%, #0a1f3a 100%);
  color: var(--text-on-dark);
  overflow: hidden;
  font-family: inherit;
}

/* Hidden but functional */
.hidden-camera {
  position: absolute;
  width: 1px; height: 1px;
  opacity: 0;
  pointer-events: none;
}
.hidden-player {
  position: absolute;
  width: 1px; height: 1px;
  opacity: 0;
  pointer-events: none;
}

/* ----- HERO ----- */
.hero {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4vh 4vw;
  z-index: 2;
}
.hero-content {
  position: relative;
  z-index: 2;
  max-width: 920px;
  text-align: center;
}
.kicker {
  display: inline-block;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 1.6rem;
}
.hero h1 {
  font-size: clamp(2.5rem, 7vw, 5.5rem);
  margin: 0 0 1.2rem;
  line-height: 1.05;
  color: var(--marista-white);
  font-weight: 800;
  letter-spacing: -0.02em;
}
.lead {
  font-size: clamp(1.1rem, 2.2vw, 1.5rem);
  color: var(--muted-on-dark);
  margin: 0 auto 2.5rem;
  max-width: 640px;
  line-height: 1.5;
}

.year-picker {
  margin: 1.5rem auto 2.5rem;
  max-width: 880px;
}
.year-track {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  max-height: 200px;
  overflow-y: auto;
  padding: 0.5rem;
}
.year-chip {
  background: rgba(255, 255, 255, 0.08);
  color: var(--marista-white);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 999px;
  padding: 0.7rem 1.3rem;
  font-size: 1.05rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, transform 0.05s;
  min-height: 50px;
}
.year-chip:hover {
  background: rgba(255, 255, 255, 0.16);
}
.year-chip.active {
  background: var(--marista-yellow);
  color: var(--marista-navy);
  border-color: var(--marista-yellow);
  transform: scale(1.05);
}

.big-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--marista-yellow);
  color: var(--marista-navy);
  font-size: 1.5rem;
  font-weight: 800;
  padding: 1.3rem 3.5rem;
  border: none;
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 10px 40px rgba(247, 201, 72, 0.35);
  transition: transform 0.1s, box-shadow 0.15s;
  min-height: 76px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.big-cta:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 14px 50px rgba(247, 201, 72, 0.5);
}
.big-cta:active:not(:disabled) { transform: scale(0.97); }
.big-cta:disabled { opacity: 0.6; cursor: not-allowed; }
.big-cta.secondary {
  background: rgba(255, 255, 255, 0.12);
  color: var(--marista-white);
  box-shadow: none;
}
.big-cta.secondary:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* Decorative blobs */
.hero-bg { position: absolute; inset: 0; pointer-events: none; z-index: 1; }
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
  animation: float 18s ease-in-out infinite;
}
.orb-1 { background: var(--marista-blue); width: 50vw; height: 50vw; top: -10vw; left: -15vw; }
.orb-2 { background: var(--marista-yellow); width: 40vw; height: 40vw; bottom: -10vw; right: -10vw; animation-delay: -6s; opacity: 0.25; }
.orb-3 { background: var(--marista-pink); width: 30vw; height: 30vw; top: 30vh; right: 10vw; animation-delay: -12s; opacity: 0.18; }
@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, -40px) scale(1.08); }
  66% { transform: translate(-30px, 30px) scale(0.95); }
}

/* ----- SLIDESHOW ----- */
.slideshow {
  position: absolute;
  inset: 0;
  z-index: 3;
  background: #000;
}
.slide-stack { position: absolute; inset: 0; }
.slide-frame {
  position: absolute;
  inset: 0;
}
/* Blurred copy fills the screen, foreground shows the whole image */
.slide-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(40px) brightness(0.55);
  transform: scale(1.15); /* hide blur edges */
}
.slide-fg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.ken-burns {
  animation: kenburns 6s ease-out forwards;
}
@keyframes kenburns {
  from { transform: scale(1.0); }
  to   { transform: scale(1.06); }
}

.slide-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  background: linear-gradient(180deg, rgba(12,44,79,0.2) 0%, rgba(12,44,79,0.75) 100%);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 6vh 4vw;
}
.search-status {
  text-align: center;
  max-width: 600px;
}
.search-status h2 {
  font-size: clamp(1.5rem, 3.5vw, 2.5rem);
  color: var(--marista-white);
  margin: 0 0 0.5rem;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.5);
}
.now-playing {
  margin: 0.4rem 0 1.2rem;
  color: var(--marista-yellow);
  font-weight: 600;
  font-size: 1.05rem;
  letter-spacing: 0.02em;
}
.progress {
  height: 6px;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 99px;
  overflow: hidden;
  max-width: 440px;
  margin: 0 auto 0.8rem;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--marista-yellow), var(--marista-blue-soft));
  transition: width 0.5s ease;
}

/* Transition between slides */
.cross-enter-active, .cross-leave-active {
  transition: opacity 1.2s ease-in-out;
}
.cross-enter-from, .cross-leave-to { opacity: 0; }

/* ----- REVEAL (foto-a-foto) ----- */
.reveal {
  position: absolute;
  inset: 0;
  z-index: 4;
  background: #000;
  cursor: pointer;
}
.reveal-stack { position: absolute; inset: 0; }
.reveal-frame {
  position: absolute;
  inset: 0;
}
.reveal-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(40px) brightness(0.5);
  transform: scale(1.15);
}
.reveal-fg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;                    /* hidden until @load fires */
  transition: opacity 0.4s ease;
}
.reveal-fg.is-loaded {
  opacity: 1;
}

/* Skeleton while the photo is downloading/decoding */
.reveal-skeleton {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(180deg, #0c2c4f 0%, #0a1f3a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 1rem;
}
.skeleton-shimmer {
  width: min(60vw, 360px);
  height: min(40vw, 240px);
  border-radius: 16px;
  background:
    linear-gradient(
      90deg,
      rgba(255, 255, 255, 0.04) 0%,
      rgba(255, 255, 255, 0.12) 50%,
      rgba(255, 255, 255, 0.04) 100%
    );
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}
.skeleton-text {
  color: rgba(255, 255, 255, 0.55);
  margin: 0;
  font-size: 0.95rem;
  letter-spacing: 0.02em;
}
@keyframes shimmer {
  0%   { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
.ken-burns-slow {
  animation: kenburns-slow 4.5s ease-out forwards;
}
@keyframes kenburns-slow {
  /* Subtle zoom — too much makes contain crop ugly */
  from { transform: scale(1.0); }
  to   { transform: scale(1.05); }
}

.reveal-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
  padding: 5vh 4vw;
  background: linear-gradient(
    180deg,
    rgba(12, 44, 79, 0.65) 0%,
    rgba(12, 44, 79, 0.15) 25%,
    rgba(12, 44, 79, 0.15) 75%,
    rgba(12, 44, 79, 0.75) 100%
  );
}
.reveal-top {
  text-align: center;
}
.reveal-top h2 {
  color: var(--marista-white);
  font-size: clamp(1.5rem, 4vw, 2.8rem);
  margin: 0.8rem 0 0.6rem;
  text-shadow: 0 2px 16px rgba(0, 0, 0, 0.6);
}
.reveal-counter {
  display: inline-block;
  background: rgba(0, 0, 0, 0.5);
  color: var(--marista-yellow);
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-weight: 700;
  letter-spacing: 0.04em;
  font-size: 0.95rem;
}
.reveal-hint {
  text-align: center;
  color: rgba(255, 255, 255, 0.75);
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.6);
}

/* Crossfade between photos in the reveal */
.reveal-cross-enter-active,
.reveal-cross-leave-active {
  transition: opacity 1s ease-in-out;
}
.reveal-cross-enter-from,
.reveal-cross-leave-to { opacity: 0; }

/* ----- RESULTS ----- */
.results {
  position: absolute;
  inset: 0;
  z-index: 4;
  background: linear-gradient(180deg, #0c2c4f 0%, #0a1f3a 100%);
  overflow-y: auto;
  padding: 4vh 4vw;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}
.results-head { text-align: center; max-width: 800px; }
.results-head h2 {
  font-size: clamp(1.8rem, 4vw, 3rem);
  color: var(--marista-white);
  margin: 0.5rem 0 0.4rem;
}
.results-head .muted {
  color: var(--muted-on-dark);
}
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.85rem;
  max-width: 1280px;
  width: 100%;
}
.result-tile {
  position: relative;
  display: block;
  aspect-ratio: 1 / 1;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 0;
  cursor: pointer;
  font: inherit;
  color: inherit;
  transition: transform 0.2s, border-color 0.15s;
}
.result-tile:hover {
  transform: scale(1.04);
  border-color: rgba(247, 201, 72, 0.5);
}
.result-tile img {
  width: 100%; height: 100%; object-fit: cover;
  display: block;
}
.video-pill {
  position: absolute;
  bottom: 6px; right: 6px;
  background: rgba(0,0,0,0.7);
  color: var(--marista-yellow);
  font-size: 0.72rem;
  padding: 2px 7px;
  border-radius: 99px;
}

/* ----- Transitions between phases ----- */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.6s ease;
}
.fade-enter-from, .fade-leave-to { opacity: 0; }

.error { color: var(--marista-yellow); margin-top: 1rem; font-weight: 600; }

/* ----- LIGHTBOX ----- */
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
  color: var(--marista-white);
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
  color: var(--marista-white);
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

.results-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: center;
  margin-top: 0.5rem;
}
.year-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 3rem 0;
}
</style>
