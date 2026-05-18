import { defineStore } from "pinia";
import { ref } from "vue";
import { meApi, type UserProfile } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

export const useProfileStore = defineStore("profile", () => {
  const profile = ref<UserProfile | null>(null);
  const loading = ref(false);
  let loadedForUser: string | null = null;

  async function load(force = false) {
    const auth = useAuthStore();
    const uid = auth.session?.user?.id ?? null;
    if (!uid) {
      profile.value = null;
      loadedForUser = null;
      return;
    }
    if (!force && loadedForUser === uid && profile.value) return;
    loading.value = true;
    try {
      profile.value = await meApi.profile();
      loadedForUser = uid;
    } catch {
      profile.value = null;
    } finally {
      loading.value = false;
    }
  }

  async function save(graduationYear: number, classLetter: string) {
    profile.value = await meApi.saveProfile(graduationYear, classLetter);
  }

  function clear() {
    profile.value = null;
    loadedForUser = null;
  }

  return { profile, loading, load, save, clear };
});
