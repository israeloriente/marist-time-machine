import { ref } from "vue";
import { alertController, loadingController, menuController, toastController } from "@ionic/vue";
import { useRoute, useRouter } from "vue-router";

export function useGlobalService() {
  const router = useRouter();
  const route = useRoute();

  const loadingActive = ref(false);
  const simpleAlertActive = ref(false);
  let loading: any = null;
  let alert: any = null;

  const goTo = (route: any) => {
    router.push(route);
  };

  const navigateRoot = (route: any) => {
    router.replace(route);
  };

  const simpleLoading = async () => {
    if (loadingActive.value) return;
    loadingActive.value = true;
    loading = await loadingController.create({
      spinner: null,
      cssClass: "spinner-carface",
      duration: 15000,
    });
    await loading.present();
    loading.onDidDismiss().then(() => {
      loadingActive.value = false;
    });
  };

  const cancelLoading = async () => {
    loading?.dismiss();
    loadingActive.value = false;
  };

  const simpleToast = async (message: string, duration: number = 3000) => {
    const toast = await toastController.create({
      message,
      duration,
      position: "bottom",
    });
    await toast.present();
  };

  const simpleAlert = async (title: string, message: string) => {
    if (simpleAlertActive.value) return;
    simpleAlertActive.value = true;
    alert = await alertController.create({
      header: title,
      message,
      mode: "ios",
      buttons: ["Ok"],
    });
    if (alert) await alert.dismiss();
    await alert.present();
    alert.onDidDismiss().then(() => (simpleAlertActive.value = false));
  };

  const confirmAlert = async (title: string, message: string, cancel?: string, ok?: string): Promise<boolean> => {
    return new Promise(async (resolve) => {
      const alert = await alertController.create({
        cssClass: "alertColor",
        mode: "ios",
        header: title,
        message: message,
        buttons: [
          {
            text: cancel || "Cancel",
            handler: () => resolve(false),
          },
          {
            text: ok || "OK",
            handler: () => resolve(true),
          },
        ],
      });
      await alert.present();
    });
  };

  const logout = () => {
    navigateRoot("/login");
    menuController.enable(false);
    // globalStore.cleanAuthToken();
  };

  const setStorage = (key: string, value: any) => {
    if (typeof value == "string") {
      const keySplited = key.split(".");
      let data: any = localStorage.getItem(keySplited[0]);

      if (data) {
        data = JSON.parse(data);
        for (let i = 1; i < keySplited.length - 1; i++) {
          data = data[keySplited[i]];
        }
        data[keySplited[keySplited.length - 1]] = value;
        localStorage.setItem(keySplited[0], JSON.stringify(data));
      } else {
        let obj: any = {};
        for (let i = keySplited.length - 1; i > 0; i--) {
          const newObj: any = {};
          newObj[keySplited[i]] = value;
          value = newObj;
          obj = newObj;
        }
        localStorage.setItem(keySplited[0], JSON.stringify(obj));
      }
    }
  };

  const getStorage = (key: string) => {
    const keySplited = key.split(".");
    let data: any = localStorage.getItem(keySplited[0]);
    if (data) {
      data = JSON.parse(data);
      for (let i = 1; i < keySplited.length; i++) {
        data = data[keySplited[i]];
      }
    }
    return data;
  };

  const resetStorage = (key: string) => {
    localStorage.removeItem(key);
  };

  return {
    goTo,
    navigateRoot,
    simpleLoading,
    cancelLoading,
    simpleToast,
    simpleAlert,
    setStorage,
    getStorage,
    resetStorage,
    confirmAlert,
    logout,
  };
}
