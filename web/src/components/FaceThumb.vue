<script setup lang="ts">
import { onMounted, ref, watch } from "vue";

const props = defineProps<{
  src: string;
  bbox: number[];   // [x1, y1, x2, y2] in source pixels
  size: number;     // output square size in CSS px (dpr-aware internally)
  padding: number;  // extra context around bbox, fraction (0.0 - 1.0)
}>();

const canvas = ref<HTMLCanvasElement | null>(null);
const error = ref(false);

async function draw() {
  if (!canvas.value) return;
  const dpr = window.devicePixelRatio || 1;
  const outPx = Math.round(props.size * dpr);
  canvas.value.width = outPx;
  canvas.value.height = outPx;
  canvas.value.style.width = props.size + "px";
  canvas.value.style.height = props.size + "px";
  const ctx = canvas.value.getContext("2d");
  if (!ctx) return;

  // background placeholder (matches --surface-strong)
  ctx.fillStyle = "#ebf3fb";
  ctx.fillRect(0, 0, outPx, outPx);

  try {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = props.src;
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("img load failed"));
    });

    const [x1, y1, x2, y2] = props.bbox;
    const bw = x2 - x1;
    const bh = y2 - y1;
    const pad = Math.max(bw, bh) * props.padding;
    const cx = (x1 + x2) / 2;
    const cy = (y1 + y2) / 2;
    const side = Math.max(bw, bh) + pad * 2;
    const sx = Math.max(0, cx - side / 2);
    const sy = Math.max(0, cy - side / 2);
    const sw = Math.min(side, img.naturalWidth - sx);
    const sh = Math.min(side, img.naturalHeight - sy);

    ctx.drawImage(img, sx, sy, sw, sh, 0, 0, outPx, outPx);
    error.value = false;
  } catch {
    error.value = true;
    // leave placeholder background
  }
}

onMounted(draw);
watch(() => [props.src, JSON.stringify(props.bbox), props.size], draw);
</script>

<template>
  <canvas ref="canvas" class="face-thumb" :class="{ error }" />
</template>

<style scoped>
.face-thumb {
  border-radius: 8px;
  background: var(--surface-strong);
  display: block;
  flex-shrink: 0;
}
.face-thumb.error {
  outline: 1px solid var(--error);
}
</style>
