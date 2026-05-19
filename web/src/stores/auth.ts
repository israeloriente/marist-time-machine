import { defineStore } from "pinia";
import { computed, ref } from "vue";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/services/supabase";

export const useAuthStore = defineStore(
  "auth",
  () => {
    const session = ref<Session | null>(null);
    const loading = ref(false);
    const error = ref<string | null>(null);

    // Read the role from app_metadata (server-controlled, NOT user-editable).
    // user_metadata is editable by the user and must never be used for authz.
    const isAdmin = computed(() => {
      const meta = session.value?.user?.app_metadata as
        | { role?: string }
        | undefined;
      return meta?.role === "admin";
    });

    async function init() {
      const { data } = await supabase.auth.getSession();
      session.value = data.session;
      supabase.auth.onAuthStateChange((_event, s) => {
        session.value = s;
      });
    }

    /** Start the Google OAuth flow. Supabase redirects the browser to
     *  Google, which redirects back to /auth/v1/callback on our Supabase
     *  domain, which then redirects to the URL we pass below. */
    async function signInWithGoogle(redirectPath = "/") {
      loading.value = true;
      error.value = null;
      try {
        const origin = window.location.origin;
        const { error: err } = await supabase.auth.signInWithOAuth({
          provider: "google",
          options: {
            redirectTo: `${origin}${redirectPath}`,
            // We don't need access to Drive/Gmail — just the identity.
            scopes: "openid email profile",
          },
        });
        if (err) throw err;
        // The browser is about to navigate to Google; nothing else to do.
      } catch (e: any) {
        error.value = e.message ?? String(e);
        loading.value = false;
      }
    }

    async function signOut() {
      await supabase.auth.signOut();
      session.value = null;
    }

    return {
      session,
      isAdmin,
      loading,
      error,
      init,
      signInWithGoogle,
      signOut,
    };
  },
  { persist: false },
);
