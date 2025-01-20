<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>Criar Conta</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <form @submit.prevent="register">
        <ion-item>
          <ion-label position="stacked">Nome</ion-label>
          <ion-input v-model="name" type="text" required></ion-input>
        </ion-item>
        <ion-item>
          <ion-label position="stacked">E-mail</ion-label>
          <ion-input v-model="email" type="email" required></ion-input>
        </ion-item>
        <ion-item>
          <ion-label position="stacked">Senha</ion-label>
          <ion-input v-model="password" type="password" required></ion-input>
        </ion-item>
        <ion-button expand="full" type="submit">Criar Conta</ion-button>
      </form>
      <ion-text color="danger">
        <p v-if="message">{{ message }}</p>
      </ion-text>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { ref } from "vue";
import {
  IonPage,
  IonHeader,
  IonToolbar,
  IonTitle,
  IonContent,
  IonItem,
  IonLabel,
  IonInput,
  IonButton,
  IonText,
} from "@ionic/vue";
import { registerUser } from "@/services/authService";

const email = ref<string>("");
const password = ref<string>("");
const name = ref<string>("");
const message = ref<string>("");

const register = async (): Promise<void> => {
  try {
    const response = await registerUser(email.value, password.value, name.value);
    message.value = "Conta criada com sucesso!";
  } catch (error: any) {
    message.value = error.message || "Erro ao criar conta.";
  }
};
</script>
