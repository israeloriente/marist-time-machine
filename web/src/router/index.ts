import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("@/views/HomeView.vue") },
    { path: "/login", name: "login", component: () => import("@/views/LoginView.vue") },
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
});
