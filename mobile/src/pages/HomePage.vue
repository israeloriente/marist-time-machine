<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>Enviar Fotos</ion-title>
        <ion-buttons slot="end">
          <ion-button v-if="images.length" @click="images = []">
            <ion-icon :icon="trashOutline"></ion-icon>
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>
    <ion-content>
      <ion-card v-for="(image, index) in images" :key="index">
        <img :src="image.preview" />
      </ion-card>
      <div class="divSubmitFile centralizeTotal" v-if="!images.length">
        <ion-icon color="marista" :icon="cloudUploadOutline"></ion-icon>
        <p>Selecione imagens de até 5MB</p>
        <ion-button @click="triggerFileInput()" expand="block"> Selecionar Imagens </ion-button>
      </div>
    </ion-content>
    <input type="file" multiple accept="image/*" ref="fileInput" style="display: none" @change="handleFileChange" />
    <ion-footer v-if="images.length">
      <ion-button @click="uploadImage()" expand="block"> Enviar Photos </ion-button>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { ref } from "vue";
import {
  IonButton,
  IonContent,
  IonButtons,
  IonFooter,
  IonPage,
  IonIcon,
  IonHeader,
  IonToolbar,
  IonTitle,
  IonCard,
} from "@ionic/vue";
import axios from "axios";
import { useUploadService } from "@/services/upload.service";
import { cloudUploadOutline, trashOutline } from "ionicons/icons";

const uploadService = useUploadService();

const images = ref<any[]>([]);
const loading = ref(true);
const error = ref();
const fileInput = ref();

// Função para construir a URL das imagens
const imageUrl = (image: any) => {
  // URL do MinIO ou do seu servidor FastAPI
  return `http://localhost:9001/mybucket/${image}`;
};

// Função para buscar imagens da API FastAPI
const fetchImages = async () => {
  try {
    const response = await axios.get("http://localhost:8000/images");
    images.value = response.data.images;
  } catch (err: any) {
    error.value = "Falha ao carregar as imagens.";
  } finally {
    loading.value = false;
  }
};

const triggerFileInput = () => {
  fileInput.value.click();
};

const handleFileChange = (event: any) => {
  const target = event.target as HTMLInputElement;
  if (!target.files?.length) return;
  images.value = Array.from(target.files)
    .filter((file: File) => file.size < 5000000)
    .map((file: File, index: number) => {
      const newName = `${new Date().toISOString()}_${index + 1}.jpg`;
      const fileWithNewName = new File([file], newName, { type: file.type });
      return {
        file: fileWithNewName,
        preview: URL.createObjectURL(fileWithNewName),
      };
    });
};

// Função para enviar a imagem
const uploadImage = async () => {
  images.value.forEach((image) => {
    uploadService.uploadImage(image.file).then((response) => {
      console.log(response);
    });
  });
};
</script>

<style scoped lang="scss">
ion-content {
  ion-card {
    width: 44%;
    float: left;
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 10px;
  }
  .divSubmitFile {
    display: flex;
    flex-direction: column;
    align-items: center;
    ion-icon {
      font-size: 100px;
    }
  }
}
ion-footer {
  padding: 5%;
}
</style>
