import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import { IonicVue } from "@ionic/vue";
import { createPinia } from "pinia";
import piniaPersist from 'pinia-plugin-persistedstate';
import "./theme/global.scss";

const pinia = createPinia();
pinia.use(piniaPersist);

const app = createApp(App);
app.use(IonicVue);
app.use(router);
app.use(pinia);

router.isReady().then(() => {
  app.mount("#app");
});
