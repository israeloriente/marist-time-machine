import { ref } from "vue";
import { useGlobalStore } from "@/store/global.store";
import axios from "axios";
import { useGlobalService } from "./global.service";

interface ResetPasswordResponse {
  message: string;
}
interface RequestResetPasswordResponse {
  message: string;
}

export function useAuthService() {
  const globalStore = useGlobalStore();
  const globalService = useGlobalService();
  const API_URL = "http://localhost:8000";

  const registerUser = async (user: any): Promise<any> => {
    return await axios.post(
      `${API_URL}/auth/register`,
      {
        email: user.email,
        password: user.password,
        name: user.name,
        phone: user.phone,
        grad_year: user.grad_year,
      },
      {
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
  };

  const loginUser = async (email: string, password: string): Promise<any> => {
    try {
      const data = new URLSearchParams();
      data.append("username", email);
      data.append("password", password);
      const response = await axios.post(`${API_URL}/auth/login`, data, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded", // Informar o tipo correto
        },
      });
      return response.data;
    } catch (error) {
      globalService.simpleAlert("Erro ao fazer login.", "Verifique suas credenciais e tente novamente.");
    }
  };

  const requestResetPassword = async (email: string): Promise<RequestResetPasswordResponse> => {
    try {
      const response = await axios.post<RequestResetPasswordResponse>(
        `${API_URL}/auth/reset_password_request`,
        { email },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );
      return response.data;
    } catch (error) {
      throw new Error("Erro ao solicitar reset de senha.");
    }
  };

  const sendResetPassword = async (code: string, newPassword: string): Promise<ResetPasswordResponse> => {
    try {
      const response = await axios.post<ResetPasswordResponse>(`${API_URL}/auth/reset_password/`, {
        new_password: newPassword,
        code,
      });
      return response.data;
    } catch (error) {
      throw new Error("Erro ao redefinir a senha.");
    }
  };

  return {
    registerUser,
    loginUser,
    requestResetPassword,
    sendResetPassword,
  };
}
