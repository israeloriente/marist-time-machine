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

// ---------- People / Faces ----------

export interface Person {
  id: string;
  display_name: string | null;
  thumbnail_face_id: string | null;
  face_count: number;
}

export interface Face {
  id: string;
  photo_id: string;
  bbox: number[]; // [x1, y1, x2, y2]
  detection_score: number;
  person_id?: string | null;
  signed_url: string;
}

export interface PersonPhoto {
  id: string;
  storage_bucket: string;
  storage_path: string;
  uploaded_at: string;
  metadata: Record<string, unknown>;
  signed_url: string;
}

export interface ClusterStats {
  faces_total: number;
  faces_clustered: number;
  people: number;
}

export interface ReclusterStatus {
  next_run_at: string | null;
  last: {
    started_at: string;
    finished_at: string;
    result?: { faces_processed: number; faces_assigned: number; people_created: number };
    error?: string;
  } | null;
}

export const peopleApi = {
  list: async (): Promise<Person[]> => (await api.get<Person[]>("/people")).data,
  stats: async (): Promise<ClusterStats> => (await api.get<ClusterStats>("/people/stats")).data,
  status: async (): Promise<ReclusterStatus> =>
    (await api.get<ReclusterStatus>("/people/recluster/status")).data,
  faces: async (personId: string): Promise<Face[]> =>
    (await api.get<Face[]>(`/people/${personId}/faces`)).data,
  photos: async (personId: string): Promise<PersonPhoto[]> =>
    (await api.get<PersonPhoto[]>(`/people/${personId}/photos`)).data,
  rename: async (personId: string, display_name: string | null): Promise<Person> =>
    (await api.patch<Person>(`/people/${personId}`, { display_name })).data,
  hide: async (personId: string, is_hidden: boolean): Promise<Person> =>
    (await api.patch<Person>(`/people/${personId}`, { is_hidden })).data,
  merge: async (sourceId: string, targetId: string): Promise<void> => {
    await api.post("/people/merge", { source_id: sourceId, target_id: targetId });
  },
  recluster: async (reset = true): Promise<{ faces_processed: number; faces_assigned: number; people_created: number }> =>
    (await api.post(`/people/recluster?reset=${reset}`)).data,
};

export const facesApi = {
  unassigned: async (limit = 100, offset = 0, min_score = 0.5): Promise<Face[]> =>
    (await api.get<Face[]>("/faces/unassigned", { params: { limit, offset, min_score } })).data,
  reassign: async (faceId: string, person_id: string | null): Promise<void> => {
    await api.patch(`/faces/${faceId}`, { person_id });
  },
  promote: async (faceId: string, display_name?: string): Promise<{ person_id: string }> =>
    (await api.post(`/faces/${faceId}/promote`, { display_name: display_name ?? null })).data,
};
