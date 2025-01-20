<template>
  <div>
    <h2>Upload de Imagem</h2>
    <form @submit.prevent="uploadImage">
      <input type="file" @change="handleFileChange" />
      <button type="submit">Enviar</button>
    </form>

    <div v-if="uploading">
      <p>Enviando imagem...</p>
    </div>

    <div v-if="message" :class="messageClass">
      <p>{{ message }}</p>
    </div>
  </div>
  <div>
    <h1>Imagens do MinIO</h1>
    <ion-button @click="fetchImages"> Listar Imagens </ion-button>
    <div v-if="loading">Carregando imagens...</div>
    <div v-if="error" class="error">Erro ao carregar imagens: {{ error }}</div>
    <div v-if="images.length > 0">
      <div v-for="(image, index) in images" :key="index">
        <img
          :src="imageUrl(image)"
          alt="Imagem"
          style="width: 200px; height: 200px; margin: 10px"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import axios from "axios";

// Definir as variáveis de estado
const file = ref(null);
const uploading = ref(false);
const message = ref("");
const messageClass = ref("");

const images = ref([]);
const loading = ref(true);
const error = ref(null);

// Função para construir a URL das imagens
const imageUrl = (image) => {
  // URL do MinIO ou do seu servidor FastAPI
  return `http://localhost:9001/mybucket/${image}`;
};

// Função para buscar imagens da API FastAPI
const fetchImages = async () => {
  try {
    const response = await axios.get("http://localhost:8000/images");
    images.value = response.data.images;
  } catch (err) {
    error.value = "Falha ao carregar as imagens.";
  } finally {
    loading.value = false;
  }
};

// Função para lidar com a seleção do arquivo
const handleFileChange = (event) => {
  file.value = event.target.files[0];
};

// Função para enviar a imagem
const uploadImage = async () => {
  if (!file.value) {
    message.value = "Por favor, selecione uma imagem para enviar.";
    messageClass.value = "error";
    return;
  }

  uploading.value = true;
  message.value = "";
  messageClass.value = "";

  const formData = new FormData();
  formData.append("file", file.value);

  try {
    const response = await axios.post(
      "http://127.0.0.1:8000/upload/",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    uploading.value = false;
    message.value = "Imagem enviada com sucesso!";
    messageClass.value = "success";
  } catch (error) {
    uploading.value = false;
    message.value = "Erro ao enviar a imagem.";
    messageClass.value = "error";
  }
};
</script>

<style scoped>
.error {
  color: red;
}

.success {
  color: green;
}
</style>
