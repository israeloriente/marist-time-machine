<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>Resetar Senha</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <ion-item>
        <ion-label position="floating">Código de Reset</ion-label>
        <ion-input
          v-model="resetCode"
          type="text"
          required
          maxlength="4"
        ></ion-input>
      </ion-item>

      <ion-item>
        <ion-label position="floating">Nova Senha</ion-label>
        <ion-input v-model="newPassword" type="password" required></ion-input>
      </ion-item>

      <ion-button expand="full" @click="resetPassword()" :disabled="isLoading">
        Resetar Senha
      </ion-button>

      <ion-toast
        v-if="message"
        :message="message"
        :duration="3000"
        :color="toastColor"
      ></ion-toast>
    </ion-content>
  </ion-page>
</template>

<script setup>
import { ref } from "vue";
import {
  IonPage,
  IonButton,
  IonItem,
  IonLabel,
  IonInput,
  IonToast,
  IonContent,
  IonHeader,
  IonToolbar,
  IonTitle,
} from "@ionic/vue";
import { useRoute, useRouter } from "vue-router";
import { sendResetPassword } from "@/services/authService";

const resetCode = ref("");
const newPassword = ref("");
const isLoading = ref(false);
const message = ref("");
const toastColor = ref("success");

const route = useRoute();
const router = useRouter();

// O email poderia ser passado via rota ou armazenado temporariamente (caso precise)
const email = route.query.email || ""; // Você pode passar o email pela URL ou usar outra abordagem

const resetPassword = async () => {
  if (!resetCode.value || !newPassword.value) {
    message.value = "Por favor, preencha todos os campos.";
    toastColor.value = "danger";
    return;
  }

  isLoading.value = true;

  sendResetPassword(resetCode.value, newPassword.value)
    .then(() => {
      message.value = "Senha resetada com sucesso!";
      toastColor.value = "success";
    })
    .catch((error) => {
      message.value = error.message || "Erro ao resetar senha.";
      toastColor.value = "danger";
    })
    .finally(() => {
      isLoading.value = false;
    });
};
</script>
