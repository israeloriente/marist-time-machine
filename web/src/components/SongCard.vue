<script setup lang="ts">
import { ref } from "vue";
import type { Song } from "@/services/api";

const props = defineProps<{
  song: Song;
  canRemove?: boolean;
}>();

const emit = defineEmits<{
  (e: "remove", id: string): void;
}>();

const playing = ref(false);
const fallback = ref(false);

function play() {
  playing.value = true;
}

function onThumbError() {
  fallback.value = true;
}

const placeholder =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 9'%3E%3Crect width='16' height='9' fill='%23ebf3fb'/%3E%3Cpath d='M6.5 3v3l3-1.5z' fill='%230c2c4f'/%3E%3C/svg%3E";
</script>

<template>
  <article class="song-card">
    <div class="player-wrap">
      <iframe
        v-if="playing"
        :src="`https://www.youtube-nocookie.com/embed/${song.youtube_id}?autoplay=1&rel=0`"
        title="YouTube player"
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        referrerpolicy="strict-origin-when-cross-origin"
        allowfullscreen
      ></iframe>
      <button v-else type="button" class="thumb-btn" :aria-label="song.title || 'Reproduzir'" @click="play">
        <img
          :src="fallback ? placeholder : (song.thumbnail_url || placeholder)"
          :alt="song.title || ''"
          loading="lazy"
          @error="onThumbError"
        />
        <span class="play-icon" aria-hidden="true">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
        </span>
      </button>
    </div>

    <div class="info">
      <div class="title-row">
        <strong class="title">{{ song.title || "Vídeo do YouTube" }}</strong>
        <span
          v-if="canRemove && song.moderation_status === 'pending'"
          class="status-badge pending"
          title="Aguardando aprovação do admin para aparecer pra todo mundo"
        >Aguardando aprovação</span>
        <span
          v-if="canRemove && song.moderation_status === 'rejected'"
          class="status-badge rejected"
          :title="song.moderation_note || 'Rejeitada pela moderação'"
        >Rejeitada</span>
      </div>
      <span v-if="song.channel" class="muted small">{{ song.channel }}</span>
      <p v-if="song.caption" class="caption">"{{ song.caption }}"</p>

      <div class="meta">
        <span v-if="song.user_graduation_year || song.user_class_letter" class="tag">
          {{ song.user_graduation_year }}
          <template v-if="song.user_class_letter">— turma {{ song.user_class_letter }}</template>
        </span>
        <a :href="song.watch_url" target="_blank" rel="noopener" class="external">↗ YouTube</a>
        <button
          v-if="canRemove"
          type="button"
          class="remove"
          title="Remover da minha lista"
          @click="emit('remove', song.id)"
        >Remover</button>
      </div>
    </div>
  </article>
</template>

<style scoped>
.song-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 8px rgba(12, 44, 79, 0.05);
}

.player-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: var(--surface-strong);
}
.player-wrap iframe {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  border: 0;
}

.thumb-btn {
  position: relative;
  width: 100%; height: 100%;
  padding: 0; border: 0;
  background: none;
  cursor: pointer;
  display: block;
}
.thumb-btn img {
  width: 100%; height: 100%; object-fit: cover; display: block;
}
.play-icon {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 64px; height: 64px;
  border-radius: 50%;
  background: rgba(12, 44, 79, 0.85);
  color: var(--marista-yellow);
  display: flex; align-items: center; justify-content: center;
  transition: transform 0.15s, background 0.15s;
}
.thumb-btn:hover .play-icon {
  transform: translate(-50%, -50%) scale(1.08);
  background: rgba(12, 44, 79, 0.95);
}

.info {
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.title {
  font-size: 1rem;
  color: var(--marista-navy);
  line-height: 1.25;
}
.caption {
  margin: 0.4rem 0 0;
  font-style: italic;
  color: var(--text);
}

.meta {
  display: flex; gap: 0.5rem; align-items: center;
  flex-wrap: wrap;
  margin-top: 0.25rem;
}
.tag {
  background: rgba(14, 109, 194, 0.12);
  color: var(--marista-blue);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.18rem 0.55rem;
  border-radius: 99px;
}
.external {
  font-size: 0.78rem;
  color: var(--muted);
  text-decoration: none;
}
.external:hover { color: var(--marista-blue); }
.remove {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--error);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
}
.remove:hover { background: rgba(214, 58, 58, 0.1); }
.small { font-size: 0.78rem; }

.title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.status-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.15rem 0.55rem;
  border-radius: 99px;
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.status-badge.pending {
  background: rgba(247, 201, 72, 0.25);
  color: #8a6913;
}
.status-badge.rejected {
  background: rgba(214, 58, 58, 0.12);
  color: var(--error);
}
</style>
