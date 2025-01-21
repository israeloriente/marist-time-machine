import { defineStore } from "pinia";

export const useGlobalStore = defineStore("global", {
  state: () => ({
    token: "",
    name: "",
    email: "",
    phone: "",
    role: "user",
  }),
  getters: {},
  actions: {
    setToken(token: string) {
      this.token = token;
    },
  },
  persist: {
    storage: localStorage,
    pick: ["token"],
  },
});
