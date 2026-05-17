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

export interface UploadResponse {
  id: string;
  storage_path: string;
  storage_bucket: string;
  uploaded_at: string;
  metadata: Record<string, unknown>;
  faces: Array<{
    id: string;
    person_id: string | null;
    bbox: number[];
    detection_score: number;
  }>;
}

export async function uploadPhoto(
  file: File,
  metadata: Record<string, unknown> = {},
  options: { onUploadProgress?: (pct: number) => void; signal?: AbortSignal } = {},
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("metadata_json", JSON.stringify(metadata));
  const { data } = await api.post<UploadResponse>("/photos", form, {
    timeout: 10 * 60 * 1000, // videos can take a while
    signal: options.signal,
    onUploadProgress: (evt) => {
      if (!options.onUploadProgress || !evt.total) return;
      options.onUploadProgress(Math.min(100, Math.round((evt.loaded / evt.total) * 100)));
    },
  });
  return data;
}
