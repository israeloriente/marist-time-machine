<script setup lang="ts">
import { computed, ref } from "vue";

const props = withDefaults(
  defineProps<{
    src: string;            // signed URL of the original media (or thumb if image-only)
    thumbSrc?: string;       // signed URL of a still image (required for videos)
    mediaType?: "image" | "video";
    alt?: string;
    showVideoControls?: boolean;  // if true, plays inline instead of just preview
  }>(),
  {
    thumbSrc: "",
    mediaType: "image",
    alt: "",
    showVideoControls: false,
  },
);

const playing = ref(false);
const isVideo = computed(() => props.mediaType === "video");
const previewSrc = computed(() => props.thumbSrc || props.src);

function play() {
  playing.value = true;
}
</script>

<template>
  <div class="media">
    <!-- Video, playing inline -->
    <video
      v-if="isVideo && (showVideoControls || playing)"
      :src="src"
      controls
      autoplay
      playsinline
      class="media-content"
    />

    <!-- Video, thumbnail with play button -->
    <button
      v-else-if="isVideo"
      type="button"
      class="media-thumb-btn"
      :title="alt || 'Reproduzir vídeo'"
      @click.stop.prevent="play"
    >
      <img :src="previewSrc" :alt="alt" loading="lazy" class="media-content" />
      <span class="play-icon" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z" />
        </svg>
      </span>
      <span class="video-badge">VÍDEO</span>
    </button>

    <!-- Image -->
    <img v-else :src="src" :alt="alt" loading="lazy" class="media-content" />
  </div>
</template>

<style scoped>
.media {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  overflow: hidden;
  background: var(--surface-strong);
}
.media-content {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.media-thumb-btn {
  position: relative;
  width: 100%;
  height: 100%;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  display: block;
  border-radius: inherit;
  overflow: hidden;
}

.play-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(12, 44, 79, 0.78);
  color: var(--marista-yellow);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  transition: transform 0.15s, background 0.15s;
}
.media-thumb-btn:hover .play-icon {
  transform: translate(-50%, -50%) scale(1.08);
  background: rgba(12, 44, 79, 0.9);
}

.video-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(12, 44, 79, 0.85);
  color: var(--marista-yellow);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 6px;
  border-radius: 4px;
  pointer-events: none;
}
</style>
