import { createRouter, createWebHistory } from "@ionic/vue-router";
import { RouteRecordRaw } from "vue-router";
import LoginPage from "@/pages/LoginPage.vue";
import HomePage from "@/pages/HomePage.vue";
import RegisterPage from "@/pages/RegisterPage.vue";
import ResetPasswordRequestPage from "@/pages/ResetPasswordRequestPage.vue";
import ResetPasswordSendPage from "@/pages/ResetPasswordSendPage.vue";

const routes: Array<RouteRecordRaw> = [
  {
    path: "/",
    redirect: "/home",
  },
  {
    path: "/home",
    name: "Home",
    component: HomePage,
  },
  {
    path: "/login",
    name: "Login",
    component: LoginPage,
  },
  {
    path: "/register",
    name: "Register",
    component: RegisterPage
  },
  {
    path: "/reset-request",
    name: "ResetRequest",
    component: ResetPasswordRequestPage
  },
  {
    path: "/reset-send",
    name: "ResetSend",
    component: ResetPasswordSendPage
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
