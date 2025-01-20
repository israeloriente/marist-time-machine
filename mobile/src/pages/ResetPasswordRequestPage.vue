<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>Solicitar Reset de Senha</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <ion-item>
        <ion-label position="floating">Email</ion-label>
        <ion-input v-model="email" type="email" required></ion-input>
      </ion-item>
      <ion-button expand="full" @click="resetPassword()" :disabled="isLoading">
        Solicitar Código
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

<script setup lang="ts">
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
import { requestResetPassword } from "@/services/authService";

const email = ref("");
const isLoading = ref(false);
const message = ref("");
const toastColor = ref("success"); // Pode ser 'success' ou 'danger' dependendo do sucesso da operação

const resetPassword = async () => {
  if (!email.value) {
    message.value = "Por favor, insira seu email.";
    toastColor.value = "danger";
    return;
  }

  isLoading.value = true;

  requestResetPassword(email.value)
    .then(() => {
      message.value = "Código de reset enviado com sucesso!";
      toastColor.value = "success";
    })
    .catch((error: any) => {
      message.value = error.message || "Erro ao solicitar reset de senha.";
      toastColor.value = "danger";
    })
    .finally(() => {
      isLoading.value = false;
    });
};
</script>
