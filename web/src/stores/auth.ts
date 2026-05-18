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

    async function signInWithEmail(email: string, password: string) {
      loading.value = true;
      error.value = null;
      try {
        const { data, error: err } = await supabase.auth.signInWithPassword({ email, password });
        if (err) throw err;
        session.value = data.session;
      } catch (e: any) {
        error.value = e.message ?? String(e);
      } finally {
        loading.value = false;
      }
    }

    async function signUpWithEmail(email: string, password: string) {
      loading.value = true;
      error.value = null;
      try {
        const { data, error: err } = await supabase.auth.signUp({ email, password });
        if (err) throw err;
        session.value = data.session;
      } catch (e: any) {
        error.value = e.message ?? String(e);
      } finally {
        loading.value = false;
      }
    }

    async function signOut() {
      await supabase.auth.signOut();
      session.value = null;
    }

    return { session, isAdmin, loading, error, init, signInWithEmail, signUpWithEmail, signOut };
  },
  { persist: false },
);
