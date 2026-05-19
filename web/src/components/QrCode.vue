<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import QRCode from "qrcode";

const props = withDefaults(
  defineProps<{
    value: string;
    size?: number;
    /** Foreground color for the QR modules. */
    color?: string;
    /** Background color. */
    background?: string;
  }>(),
  {
    size: 140,
    color: "#0c2c4f",
    background: "#ffffff",
  },
);

const svg = ref<string>("");

async function generate() {
  try {
    svg.value = await QRCode.toString(props.value, {
      type: "svg",
      errorCorrectionLevel: "M",
      margin: 1,
      color: { dark: props.color, light: props.background },
    });
  } catch {
    svg.value = "";
  }
}

watch(
  () => [props.value, props.color, props.background],
  () => generate(),
);

onMounted(generate);
</script>

<template>
  <div
    class="qr"
    :style="{ width: `${size}px`, height: `${size}px`, background }"
    aria-hidden="true"
    v-html="svg"
  />
</template>

<style scoped>
.qr {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  padding: 0;
  overflow: hidden;
}
.qr :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
