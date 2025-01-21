import { useGlobalStore } from "@/store/global.store";
import axios from "axios";

export function useUploadService() {
  const globalStore = useGlobalStore();
  const API_URL = "http://localhost:8000";

  const uploadImage = async (file: any) => {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await axios.post("http://localhost:8000/upload/", formData, {
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

  return {
    uploadImage,
  };
}
