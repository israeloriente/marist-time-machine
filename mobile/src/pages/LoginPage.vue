<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>{{ isLogin ? "Login" : "Criar Conta" }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <form @submit.prevent="action" class="centralizeTotal">
        <div v-if="isLogin">
          <img src="@/assets/marista.png" />
          <ion-item>
            <ion-label position="stacked">E-mail</ion-label>
            <ion-input v-model="user.email" type="email" required></ion-input>
          </ion-item>
          <ion-item>
            <ion-label position="stacked">Senha</ion-label>
            <ion-input v-model="user.password" type="password" required></ion-input>
          </ion-item>
          <ion-button class="mt-4" expand="block" type="submit">Entrar</ion-button>
          <ion-button class="mt-2" expand="block" fill="outline" @click="isLogin = !isLogin">Cadastrar</ion-button>
        </div>
        <div v-else>
          <ion-item>
            <ion-label position="stacked">Nome Completo</ion-label>
            <ion-input v-model="user.name" type="text" required></ion-input>
          </ion-item>
          <ion-item>
            <ion-label position="stacked">Telefone</ion-label>
            <ion-input v-model="user.phone" type="tel" required></ion-input>
          </ion-item>
          <ion-item>
            <ion-label position="stacked">Ano de Conclusão</ion-label>
            <ion-select v-model="user.grad_year" interface="action-sheet" placeholder="Selecione o ano">
              <ion-select-option v-for="year in years" :key="year" :value="year">
                Eu me formei no Marista em {{ year }}
              </ion-select-option>
            </ion-select>
          </ion-item>
          <ion-item>
            <ion-label position="stacked">E-mail</ion-label>
            <ion-input v-model="user.email" type="email" required></ion-input>
          </ion-item>
          <ion-item>
            <ion-label position="stacked">Senha</ion-label>
            <ion-input v-model="user.password" type="password" required></ion-input>
          </ion-item>
          <ion-item>
            <ion-label position="stacked">Repetir Senha</ion-label>
            <ion-input v-model="repeatPassword" type="password" required></ion-input>
          </ion-item>
          <ion-button expand="block" type="submit" :disabled="!formIsValid">Criar Conta</ion-button>
          <ion-button class="mt-2" expand="block" fill="outline" @click="isLogin = !isLogin">Já tem conta? faça login</ion-button>
        </div>
      </form>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  IonPage,
  IonHeader,
  IonToolbar,
  IonSelect,
  IonSelectOption,
  IonTitle,
  IonContent,
  IonItem,
  IonLabel,
  IonInput,
  IonButton,
} from "@ionic/vue";
import { useGlobalService } from "@/services/global.service";
import { useAuthService } from "@/services/auth.service";
import { useGlobalStore } from "@/store/global.store";

const globalService = useGlobalService();
const globalStore = useGlobalStore();
const authService = useAuthService();

const user = ref({
  name: "Israel Oriente",
  email: "israelnunesoriente@gmail.com",
  phone: "123",
  password: "0i0i0i",
  grad_year: 2016,
});
const repeatPassword = ref<string>("0i0i0i");
const isLogin = ref<boolean>(true);
const currentYear = new Date().getFullYear();
const years = Array.from({ length: 101 }, (_, i) => currentYear - i);

onMounted(() => {});

const formIsValid = computed(() => {
  return (
    user.value.password === repeatPassword.value &&
    user.value.password.length > 0 &&
    user.value.email.length > 0 &&
    user.value.name.length > 0 &&
    user.value.phone.length > 0 &&
    user.value.grad_year > 0
  );
});

const action = () => {
  isLogin.value ? login() : register();
};
const login = async (): Promise<void> => {
  authService.loginUser(user.value.email, user.value.password).then((res) => {
    globalStore.setToken(res.access_token);
    globalService.simpleToast("Login efetuado com sucesso!");
    globalService.navigateRoot("/tabs");
  });
};
const register = async (): Promise<void> => {
  authService
    .registerUser(user.value)
    .then((res) => {
      globalService.simpleToast("Conta criada com sucesso!");
      isLogin.value = true;
    })
    .catch((error) => {
      const err = error?.response?.data?.detail;
      if (err) globalService.simpleAlert("Erro ao criar conta", err);
      else globalService.simpleToast("Erro ao criar conta. Tente novamente.");
    });
};
</script>

<style scoped lang="scss">
form {
  width: 90%;
  max-width: 350px;
  img {
    width: 130px;
    display: block;
    margin: auto;
    margin-bottom: 10%;
  }
}
</style>
