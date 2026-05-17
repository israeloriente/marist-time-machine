import axios from "axios";
import { supabase } from "./supabase";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface MatchedPhoto {
  photo_id: string;
  storage_bucket: string;
  storage_path: string;
  uploaded_at: string;
  signed_url: string;
  distance: number;
}

export interface SearchResponse {
  person_id: string | null;
  matched_faces: number;
  photos: MatchedPhoto[];
}

export async function searchByFace(file: Blob): Promise<SearchResponse> {
  const form = new FormData();
  form.append("file", file, "selfie.jpg");
  const { data } = await api.post<SearchResponse>("/search", form);
  return data;
}

export async function uploadPhoto(file: File, metadata: Record<string, unknown> = {}) {
  const form = new FormData();
  form.append("file", file);
  form.append("metadata_json", JSON.stringify(metadata));
  const { data } = await api.post("/photos", form);
  return data;
}
