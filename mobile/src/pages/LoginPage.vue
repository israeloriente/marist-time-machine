<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>Login</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <form @submit.prevent="login">
        <ion-item>
          <ion-label position="stacked">E-mail</ion-label>
          <ion-input v-model="email" type="email" required></ion-input>
        </ion-item>
        <ion-item>
          <ion-label position="stacked">Senha</ion-label>
          <ion-input v-model="password" type="password" required></ion-input>
        </ion-item>
        <ion-button expand="full" type="submit">Login</ion-button>
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
import { loginUser } from "@/services/authService";

const email = ref<string>("");
const password = ref<string>("");
const message = ref<string>("");

const login = async (): Promise<void> => {
	console.log(email.value, password.value);

  try {
    const response = await loginUser(email.value, password.value);
    message.value = "Login realizado com sucesso!";
    localStorage.setItem("token", response.token);
  } catch (error: any) {
    message.value = error.message || "Erro ao realizar o login.";
  }
};
</script>
