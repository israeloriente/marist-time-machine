import { createApp } from "vue";
import { createPinia } from "pinia";
import piniaPersist from "pinia-plugin-persistedstate";
import App from "./App.vue";
import { router } from "./router";
import { registerSW } from "virtual:pwa-register";

import "./styles/main.css";

registerSW({ immediate: true });

const app = createApp(App);
const pinia = createPinia();
pinia.use(piniaPersist);
app.use(pinia);
app.use(router);
app.mount("#app");

// Hide the inline splash screen only after:
// - Vue mounted (#app has content)
// - Initial route component finished resolving (router.isReady)
// - One animation frame painted so first layout is in
// - On /kiosk routes, give a small additional buffer so the hero appears
//   ready (background blobs animation, year chips, etc) instead of popping.
async function hideSplash() {
  try {
    await router.isReady();
  } catch {
    /* ignore — splash hides anyway */
  }
  await new Promise<void>((r) => requestAnimationFrame(() => r()));
  // For kiosk give one extra paint cycle so chips/animations show in place
  const isKiosk = window.location.pathname.startsWith("/kiosk");
  if (isKiosk) {
    await new Promise<void>((r) => setTimeout(r, 250));
  }
  document.body.classList.add("app-ready");
  // Remove from DOM after the fade-out finishes
  setTimeout(() => {
    const el = document.getElementById("mtm-splash");
    el?.parentNode?.removeChild(el);
  }, 600);
}
hideSplash();
