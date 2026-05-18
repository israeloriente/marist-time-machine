import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useProfileStore } from "@/stores/profile";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("@/views/HomeView.vue") },
    { path: "/login", name: "login", component: () => import("@/views/LoginView.vue") },
    {
      path: "/kiosk",
      name: "kiosk",
      component: () => import("@/views/KioskView.vue"),
      // intentionally NO requiresAuth — this is the public touchscreen page
    },
    {
      path: "/onboarding",
      name: "onboarding",
      component: () => import("@/views/OnboardingView.vue"),
      meta: { requiresAuth: true, skipProfileCheck: true },
    },
    {
      path: "/perfil",
      name: "profile",
      component: () => import("@/views/ProfileView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/capture",
      name: "capture",
      component: () => import("@/views/CaptureView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/upload",
      name: "upload",
      component: () => import("@/views/UploadView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/results",
      name: "results",
      component: () => import("@/views/ResultsView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/contribute",
      name: "contribute",
      component: () => import("@/views/ContributeView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/musicas",
      name: "songs",
      component: () => import("@/views/SongsView.vue"),
      meta: { requiresAuth: true },
    },
    {
      // Admin section with sidebar layout
      path: "/admin",
      component: () => import("@/layouts/AdminLayout.vue"),
      meta: { requiresAuth: true },
      children: [
        {
          path: "",
          name: "admin",
          component: () => import("@/views/admin/AdminDashboardView.vue"),
        },
        {
          path: "pessoas",
          name: "admin-people",
          component: () => import("@/views/admin/AdminPeopleView.vue"),
        },
        {
          path: "nao-atribuidos",
          name: "admin-unassigned",
          component: () => import("@/views/admin/AdminUnassignedView.vue"),
        },
        {
          path: "fotos",
          name: "admin-photos",
          component: () => import("@/views/admin/AdminPhotosView.vue"),
        },
        {
          path: "musicas",
          name: "admin-songs",
          component: () => import("@/views/admin/AdminSongsView.vue"),
        },
        {
          path: "sugestoes",
          name: "admin-suggestions",
          component: () => import("@/views/admin/AdminSuggestionsView.vue"),
        },
        {
          path: "status",
          name: "admin-status",
          component: () => import("@/views/admin/AdminStatusView.vue"),
        },
        {
          path: "pessoas/:id",
          name: "person",
          component: () => import("@/views/PersonView.vue"),
        },
      ],
    },
    // Legacy redirect (old /people/:id link)
    {
      path: "/people/:id",
      redirect: (to) => ({ name: "person", params: { id: to.params.id } }),
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.session) await auth.init();
  if (to.meta.requiresAuth && !auth.session) {
    return { name: "login", query: { redirect: to.fullPath } };
  }

  // Profile gate: authenticated users without a saved profile go to /onboarding.
  // Routes can opt out via meta.skipProfileCheck (the onboarding page itself).
  if (auth.session && to.meta.requiresAuth && !to.meta.skipProfileCheck) {
    const profile = useProfileStore();
    await profile.load();
    if (!profile.profile) {
      return { name: "onboarding", query: { redirect: to.fullPath } };
    }
  }
});
