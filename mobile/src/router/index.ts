import { createRouter } from "@ionic/vue-router";
import { createWebHashHistory, RouteRecordRaw } from "vue-router";
import LoginPage from "@/pages/LoginPage.vue";
import TabsPage from "@/pages/TabsPage.vue";
import ResetPasswordRequestPage from "@/pages/ResetPasswordRequestPage.vue";
import ResetPasswordSendPage from "@/pages/ResetPasswordSendPage.vue";

const routes: Array<RouteRecordRaw> = [
  {
    path: "/",
    redirect: "/home",
  },
  {
    path: "/tabs",
    name: "Tabs",
    component: TabsPage,
  },
  {
    path: "/login",
    name: "Login",
    component: LoginPage,
  },
  {
    path: "/reset-request",
    name: "ResetRequest",
    component: ResetPasswordRequestPage,
  },
  {
    path: "/reset-send",
    name: "ResetSend",
    component: ResetPasswordSendPage,
  },
];

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
