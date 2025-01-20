import axios from "axios";

// Definindo a URL do backend
const API_URL = "http://localhost:8000"; // URL do backend

// Tipos para as respostas das APIs
interface AuthResponse {
  token: string;
  user: {
    email: string;
    id: string;
  };
}

interface ResetPasswordResponse {
  message: string;
}

interface RequestResetPasswordResponse {
  message: string;
}

// Função para registrar o usuário
export const registerUser = async (
  email: string,
  password: string,
  name: string
): Promise<AuthResponse> => {
  try {
    const response = await axios.post<AuthResponse>(
      `${API_URL}/auth/register`,
      { email, password, name }
    );
    return response.data;
  } catch (error) {
    throw new Error("Erro ao criar conta.");
  }
};

export const loginUser = async (
  email: string,
  password: string
): Promise<AuthResponse> => {
  try {
    const data = new URLSearchParams();
    data.append("username", email);
    data.append("password", password);
    const response = await axios.post<AuthResponse>(
      `${API_URL}/auth/login`,
      data,
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded", // Informar o tipo correto
        },
      }
    );
    return response.data;
  } catch (error) {
    throw new Error("E-mail ou senha incorretos.");
  }
};

// Função para solicitar recuperação de senha
export const requestResetPassword = async (
  email: string
): Promise<RequestResetPasswordResponse> => {
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

// Função para redefinir a senha
export const sendResetPassword = async (
  code: string,
  newPassword: string
): Promise<ResetPasswordResponse> => {
  try {
    const response = await axios.post<ResetPasswordResponse>(
      `${API_URL}/auth/reset_password/`,
      { new_password: newPassword, code }
    );
    return response.data;
  } catch (error) {
    throw new Error("Erro ao redefinir a senha.");
  }
};
