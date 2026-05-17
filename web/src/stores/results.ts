import { defineStore } from "pinia";
import { ref } from "vue";
import type { SearchResponse } from "@/services/api";

export const useResultsStore = defineStore(
  "results",
  () => {
    const data = ref<SearchResponse | null>(null);
    function set(r: SearchResponse) {
      data.value = r;
    }
    function clear() {
      data.value = null;
    }
    return { data, set, clear };
  },
  { persist: true },
);
