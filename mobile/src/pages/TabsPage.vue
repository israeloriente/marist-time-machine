<template>
  <ion-page>
    <ion-content>
      <ion-tabs>
        <ion-tab tab="home">
          <HomePage />
        </ion-tab>

        <ion-tab tab="search">
          <ion-content>
            <h2>Search Tab</h2>
            <ion-button @click="teste()">Add Embedding</ion-button>
            <div>
              <input type="file" @change="handleFileChange" />
              <button @click="compareImage">Comparar Imagem</button>
            </div>
            <div v-for="(photo, index) in photos" :key="index">
              <img :src="photo.image_url" alt="Imagem" style="width: 200px; height: 200px; margin: 10px" />
            </div>
          </ion-content>
        </ion-tab>

        <ion-tab tab="musics">
          <ion-content>
            <h2>Musics Tab</h2>
          </ion-content>
        </ion-tab>

        <ion-tab tab="settings">
          <ion-content>
            <h2>Settings Tab</h2>
          </ion-content>
        </ion-tab>

        <ion-tab-bar slot="bottom">
          <ion-tab-button tab="home">
            <ion-icon :icon="cloudUploadOutline"></ion-icon>
            <ion-label>Enviar</ion-label>
          </ion-tab-button>

          <ion-tab-button tab="search">
            <ion-icon :icon="listOutline"></ion-icon>
            <ion-label>Imagens</ion-label>
          </ion-tab-button>

          <ion-tab-button tab="musics">
            <ion-icon :icon="musicalNoteOutline"></ion-icon>
            <ion-label>Músicas</ion-label>
          </ion-tab-button>

          <ion-tab-button tab="settings">
            <ion-icon :icon="personOutline"></ion-icon>
            <ion-label>Perfil</ion-label>
          </ion-tab-button>
        </ion-tab-bar>
      </ion-tabs>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { IonTab, IonContent, IonIcon, IonButton, IonTabButton, IonTabs, IonLabel, IonTabBar, IonPage } from "@ionic/vue";
import { cloudUploadOutline, listOutline, musicalNoteOutline, personOutline } from "ionicons/icons";
import HomePage from "./HomePage.vue";
import axios from "axios";
import { useGlobalStore } from "@/store/global.store";
import { ref } from "vue";

const globalStore = useGlobalStore();

const selectedFile = ref();
const photos = ref<any[]>([]);

const handleFileChange = (event: any) => {
  const file = event.target.files[0]; // Pega o primeiro arquivo da lista
  if (file) {
    selectedFile.value = file; // Armazena o arquivo
  }
};

// Método para comparar a imagem
const compareImage = () => {
  if (!selectedFile.value) {
    alert("Por favor, selecione uma imagem primeiro.");
    return;
  }

  // Converte o arquivo para base64
  const reader: any = new FileReader();
  reader.onloadend = async () => {
    const base64Image = reader.result.split(",")[1]; // Remove o prefixo "data:image/jpeg;base64,"

    try {
      const { similar_faces } = await similar(base64Image); // Chama a função similar passando o base64
      photos.value = similar_faces; // Atualiza a lista de fotos
      console.log(photos.value);
    } catch (error) {
      console.error("Erro ao comparar a imagem:", error);
    }
  };

  reader.readAsDataURL(selectedFile.value); // Converte o arquivo em base64
};

const similar = async (base64Image: string) => {
  try {
    const response = await axios.post(
      "http://localhost:8000/compare-embedding/",
      {
        image: base64Image, // Envia a imagem em base64 para o backend
      },
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${globalStore.token}`, // Se necessário
        },
      }
    );
    return response.data; // Retorna os resultados das faces similares
  } catch (error: any) {
    throw new Error("Erro ao processar a imagem: " + (error.response ? error.response.data : error.message));
  }
};

const teste = async () => {
  try {
    const response = await axios.post("http://localhost:8000/add-embedding/", {
      headers: {
        "Content-Type": "multipart/form-data", // Importante para envio de arquivos
        Authorization: `Bearer ${globalStore.token}`, // Passa o token JWT no header de autenticação
      },
    });
    return response;
  } catch (error) {
    // console.error("Error uploading file:", error.response ? error.response.data : error.message);
    throw new Error("Erro ao fazer upload do arquivo");
  }
};
</script>

<style scoped></style>
