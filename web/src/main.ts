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
