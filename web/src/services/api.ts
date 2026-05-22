import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { supabase } from "./supabase";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

// Refresh the access token if it expires within this many seconds. Long
// uploads (videos, batches) can otherwise outlive a token captured at
// request-start time.
const REFRESH_LEEWAY_SECONDS = 120;

let refreshInFlight: Promise<string | null> | null = null;

async function getFreshToken(force = false): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  const session = data.session;
  if (!session) return null;

  const expiresAt = session.expires_at ?? 0; // unix seconds
  const now = Math.floor(Date.now() / 1000);
  const needsRefresh = force || expiresAt - now < REFRESH_LEEWAY_SECONDS;
  if (!needsRefresh) return session.access_token;

  // De-dupe concurrent refreshes (parallel uploads all hit the interceptor
  // at once — one refresh, the rest reuse the result).
  if (!refreshInFlight) {
    refreshInFlight = supabase.auth
      .refreshSession()
      .then(({ data: refreshed }) => refreshed.session?.access_token ?? null)
      .catch(() => session.access_token ?? null)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

api.interceptors.request.use(async (config) => {
  const token = await getFreshToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// One-shot retry on 401: refresh the token and replay the original request.
// Guards against infinite loops by marking the config.
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as
      | (InternalAxiosRequestConfig & { _retriedAfterRefresh?: boolean })
      | undefined;
    const status = error.response?.status;
    if (status !== 401 || !config || config._retriedAfterRefresh) {
      return Promise.reject(error);
    }
    const token = await getFreshToken(true);
    if (!token) return Promise.reject(error);
    config._retriedAfterRefresh = true;
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
    return api.request(config);
  },
);

export interface MatchedPhoto {
  photo_id: string;
  storage_bucket: string;
  storage_path: string;
  uploaded_at: string;
  signed_url: string;
  thumb_signed_url: string;
  media_type: "image" | "video";
  distance: number;
}

export interface SearchResponse {
  person_id: string | null;
  display_name: string | null;
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
  duplicate?: boolean;
  moderation_status?: "pending" | "approved" | "rejected";
  pending?: boolean;
}

// ---------- Photo moderation ----------

export interface PhotoModerationItem {
  id: string;
  storage_bucket: string;
  storage_path: string;
  uploaded_at: string;
  uploaded_by: string | null;
  uploader_email: string | null;
  metadata: Record<string, unknown>;
  media_type: "image" | "video";
  signed_url: string;
  thumb_signed_url: string;
  moderation_status: "pending" | "approved" | "rejected";
  moderation_note: string | null;
  moderated_at: string | null;
  face_count: number;
}

export interface ModerationCounts {
  pending: number;
  approved: number;
  rejected: number;
}

export const moderationApi = {
  list: async (
    status_filter: "pending" | "approved" | "rejected" = "pending",
    limit = 100,
    offset = 0,
  ): Promise<PhotoModerationItem[]> =>
    (
      await api.get<PhotoModerationItem[]>("/photos/moderation", {
        params: { status_filter, limit, offset },
      })
    ).data,
  counts: async (): Promise<ModerationCounts> =>
    (await api.get<ModerationCounts>("/photos/moderation/counts")).data,
  approve: async (id: string, note?: string): Promise<PhotoModerationItem> =>
    (await api.post<PhotoModerationItem>(`/photos/${id}/approve`, { note: note ?? null })).data,
  reject: async (id: string, note?: string): Promise<PhotoModerationItem> =>
    (await api.post<PhotoModerationItem>(`/photos/${id}/reject`, { note: note ?? null })).data,
  deleteForever: async (
    id: string,
  ): Promise<{
    deleted: boolean;
    photo_id: string;
    faces_removed: number;
    objects_removed: string[];
  }> => (await api.delete(`/photos/${id}`)).data,
  bulkApprove: async (photo_ids: string[], note?: string): Promise<BulkResult> =>
    (await api.post<BulkResult>("/photos/moderation/bulk-approve", {
      photo_ids, note: note ?? null,
    })).data,
  bulkReject: async (photo_ids: string[], note?: string): Promise<BulkResult> =>
    (await api.post<BulkResult>("/photos/moderation/bulk-reject", {
      photo_ids, note: note ?? null,
    })).data,
  bulkDelete: async (photo_ids: string[]): Promise<BulkResult> =>
    (await api.post<BulkResult>("/photos/moderation/bulk-delete", {
      photo_ids,
    })).data,
};

export interface BulkResult {
  succeeded: string[];
  failed: Array<{ id: string; reason: string }>;
}

export async function dedupePhotos(): Promise<{
  photos_visited: number;
  hashed: number;
  duplicates_removed: number;
  errors: number;
}> {
  const { data } = await api.post("/photos/dedupe", null, { timeout: 30 * 60 * 1000 });
  return data;
}

export interface RandomPhoto {
  id: string;
  signed_url: string;
  thumb_signed_url: string;
}

export async function randomPhotos(limit = 30, year?: number): Promise<RandomPhoto[]> {
  const params: Record<string, string | number> = { limit };
  if (year !== undefined) params.year = year;
  const { data } = await api.get<RandomPhoto[]>("/photos/random", { params });
  return data;
}

export interface PublicStats {
  photos: number;
  named_people: number;
  years: number;
  oldest_year: number | null;
}

export async function publicStats(): Promise<PublicStats> {
  const { data } = await api.get<PublicStats>("/photos/stats/public");
  return data;
}

export async function regenerateVideoThumbnails(): Promise<{
  videos_visited: number;
  thumbnails_generated: number;
  errors: number;
}> {
  const { data } = await api.post("/photos/regenerate-thumbnails", null, {
    timeout: 30 * 60 * 1000,
  });
  return data;
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
  status?: "active" | "rejected";
  // Canonical (admin/community-curated)
  graduation_year?: number | null;
  class_letter?: string | null;
  // Derived from photo metadata (fallback)
  graduation_years?: number[];
  classes?: string[];
  // Embedded thumbnail face (no extra /faces round-trip needed)
  thumb_signed_url?: string | null;
  thumb_bbox?: number[] | null;
}

export interface PeopleFilters {
  year?: number;
  class?: string;
  status?: "active" | "rejected";
}

export interface AvailableFilters {
  years: number[];
  classes: string[];
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
  media_type: "image" | "video";
  signed_url: string;
  thumb_signed_url: string;
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
  list: async (filters: PeopleFilters = {}): Promise<Person[]> => {
    const params: Record<string, string | number> = {};
    if (filters.year !== undefined) params.year = filters.year;
    if (filters.class) params.class = filters.class;
    if (filters.status) params.status = filters.status;
    return (await api.get<Person[]>("/people", { params })).data;
  },
  get: async (personId: string): Promise<Person> =>
    (await api.get<Person>(`/people/${personId}`)).data,
  filters: async (): Promise<AvailableFilters> =>
    (await api.get<AvailableFilters>("/people/filters")).data,
  stats: async (): Promise<ClusterStats> => (await api.get<ClusterStats>("/people/stats")).data,
  status: async (): Promise<ReclusterStatus> =>
    (await api.get<ReclusterStatus>("/people/recluster/status")).data,
  faces: async (personId: string): Promise<Face[]> =>
    (await api.get<Face[]>(`/people/${personId}/faces`)).data,
  photos: async (personId: string): Promise<PersonPhoto[]> =>
    (await api.get<PersonPhoto[]>(`/people/${personId}/photos`)).data,
  rename: async (personId: string, display_name: string | null): Promise<Person> =>
    (await api.patch<Person>(`/people/${personId}`, { display_name })).data,
  setStatus: async (
    personId: string,
    status: "active" | "rejected",
  ): Promise<Person> =>
    (await api.patch<Person>(`/people/${personId}`, { status })).data,
  updateGraduation: async (
    personId: string,
    graduation_year: number | null,
    class_letter: string | null,
  ): Promise<Person> =>
    (await api.patch<Person>(`/people/${personId}`, {
      graduation_year,
      class_letter,
    })).data,
  merge: async (sourceId: string, targetId: string): Promise<void> => {
    await api.post("/people/merge", { source_id: sourceId, target_id: targetId });
  },
  recluster: async (reset = true): Promise<{ faces_processed: number; faces_assigned: number; people_created: number }> =>
    (await api.post(`/people/recluster?reset=${reset}`)).data,
};

export const facesApi = {
  unassigned: async (
    limit = 100,
    offset = 0,
    min_score = 0.5,
    rejected = false,
  ): Promise<Face[]> =>
    (
      await api.get<Face[]>("/faces/unassigned", {
        params: { limit, offset, min_score, rejected },
      })
    ).data,
  reassign: async (faceId: string, person_id: string | null): Promise<void> => {
    await api.patch(`/faces/${faceId}`, { person_id });
  },
  promote: async (faceId: string, display_name?: string): Promise<{ person_id: string }> =>
    (await api.post(`/faces/${faceId}/promote`, { display_name: display_name ?? null })).data,
  reject: async (faceId: string, rejected: boolean): Promise<void> => {
    await api.post(`/faces/${faceId}/reject`, { rejected });
  },
};

// ---------- Name suggestions (crowd-sourced) ----------

export interface SuggestionGroup {
  person_id: string | null;
  face_id: string | null;
  suggested_name: string;
  normalized_name: string;
  suggested_graduation_year?: number | null;
  suggested_class_letter?: string | null;
  vote_count: number;
  first_suggested_at: string;
  last_suggested_at: string;
  suggestion_ids: string[];
}

export interface NameVote {
  suggestion_id: string;
  suggested_name: string;
  normalized_name: string;
  suggested_graduation_year?: number | null;
  suggested_class_letter?: string | null;
  vote_count: number;
  first_at: string;
  last_at: string;
}

export interface TargetWithSuggestions {
  person_id: string | null;
  face_id: string | null;
  face_count: number;
  detection_score: number;
  thumb_signed_url: string | null;
  thumb_bbox: number[] | null;
  names: NameVote[];
}

// ---------- Current user profile ----------

export interface UserProfile {
  user_id: string;
  graduation_year: number;
  class_letter: string;
  terms_accepted_at: string | null;
  terms_version: string | null;
  created_at: string;
  updated_at: string;
}

export const meApi = {
  profile: async (): Promise<UserProfile | null> =>
    (await api.get<UserProfile | null>("/me/profile")).data,
  saveProfile: async (
    graduation_year: number,
    class_letter: string,
    accept_terms = false,
  ): Promise<UserProfile> =>
    (
      await api.put<UserProfile>("/me/profile", {
        graduation_year,
        class_letter,
        accept_terms,
      })
    ).data,
};

// ---------- Reports (denúncia de mídia) ----------

export interface Report {
  id: string;
  reporter_id: string | null;
  reporter_email: string | null;
  photo_id: string | null;
  face_id: string | null;
  reason: string;
  contact_info: string | null;
  status: "pending" | "resolved_removed" | "resolved_rejected";
  resolution_note: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
  photo_signed_url: string | null;
  photo_thumb_signed_url: string | null;
  uploader_email: string | null;
}

export interface ReportCounts {
  pending: number;
  resolved_removed: number;
  resolved_rejected: number;
}

export const reportsApi = {
  create: async (input: {
    photo_id?: string;
    face_id?: string;
    reason: string;
    contact_info?: string;
  }): Promise<Report> =>
    (
      await api.post<Report>("/reports", {
        photo_id: input.photo_id ?? null,
        face_id: input.face_id ?? null,
        reason: input.reason,
        contact_info: input.contact_info ?? null,
      })
    ).data,
  mine: async (): Promise<Report[]> =>
    (await api.get<Report[]>("/reports/mine")).data,
  list: async (
    status: "pending" | "resolved_removed" | "resolved_rejected" = "pending",
    limit = 100,
    offset = 0,
  ): Promise<Report[]> =>
    (await api.get<Report[]>("/reports", { params: { status, limit, offset } }))
      .data,
  counts: async (): Promise<ReportCounts> =>
    (await api.get<ReportCounts>("/reports/counts")).data,
  resolve: async (
    id: string,
    action: "remove" | "reject",
    note?: string,
  ): Promise<Report> =>
    (
      await api.post<Report>(`/reports/${id}/resolve`, {
        action,
        note: note ?? null,
      })
    ).data,
};

// ---------- Songs (trilha sonora) ----------

export interface Song {
  id: string;
  user_id: string;
  youtube_id: string;
  title: string | null;
  channel: string | null;
  caption: string | null;
  thumbnail_url: string | null;
  watch_url: string;
  created_at: string;
  moderation_status: "pending" | "approved" | "rejected";
  moderation_note: string | null;
  moderated_at: string | null;
  user_email: string | null;
  user_graduation_year: number | null;
  user_class_letter: string | null;
}

export const songsApi = {
  list: async (filters: { year?: number; class?: string; user_id?: string } = {}): Promise<Song[]> => {
    const params: Record<string, string | number> = {};
    if (filters.year !== undefined) params.year = filters.year;
    if (filters.class) params.class = filters.class;
    if (filters.user_id) params.user_id = filters.user_id;
    return (await api.get<Song[]>("/songs", { params })).data;
  },
  random: async (year?: number, limit = 20): Promise<Song[]> => {
    const params: Record<string, string | number> = { limit };
    if (year !== undefined) params.year = year;
    return (await api.get<Song[]>("/songs/random", { params })).data;
  },
  mine: async (): Promise<Song[]> => (await api.get<Song[]>("/songs/mine")).data,
  create: async (url: string, caption?: string): Promise<Song> =>
    (await api.post<Song>("/songs", { url, caption: caption ?? null })).data,
  update: async (id: string, caption: string | null): Promise<Song> =>
    (await api.patch<Song>(`/songs/${id}`, { caption })).data,
  remove: async (id: string): Promise<void> => {
    await api.delete(`/songs/${id}`);
  },
};

export const songsModerationApi = {
  list: async (
    status_filter: "pending" | "approved" | "rejected" = "pending",
    limit = 100,
    offset = 0,
  ): Promise<Song[]> =>
    (
      await api.get<Song[]>("/songs/moderation", {
        params: { status_filter, limit, offset },
      })
    ).data,
  counts: async (): Promise<ModerationCounts> =>
    (await api.get<ModerationCounts>("/songs/moderation/counts")).data,
  approve: async (id: string, note?: string): Promise<Song> =>
    (await api.post<Song>(`/songs/${id}/approve`, { note: note ?? null })).data,
  reject: async (id: string, note?: string): Promise<Song> =>
    (await api.post<Song>(`/songs/${id}/reject`, { note: note ?? null })).data,
  bulkApprove: async (song_ids: string[], note?: string): Promise<BulkResult> =>
    (
      await api.post<BulkResult>("/songs/moderation/bulk-approve", {
        song_ids,
        note: note ?? null,
      })
    ).data,
  bulkReject: async (song_ids: string[], note?: string): Promise<BulkResult> =>
    (
      await api.post<BulkResult>("/songs/moderation/bulk-reject", {
        song_ids,
        note: note ?? null,
      })
    ).data,
  bulkDelete: async (song_ids: string[]): Promise<BulkResult> =>
    (
      await api.post<BulkResult>("/songs/moderation/bulk-delete", {
        song_ids,
      })
    ).data,
};

export const suggestionsApi = {
  create: async (
    target: { person_id?: string; face_id?: string },
    suggested_name: string,
    extras?: { suggested_graduation_year?: number | null; suggested_class_letter?: string | null },
  ) =>
    (
      await api.post("/suggestions", {
        ...target,
        suggested_name,
        suggested_graduation_year: extras?.suggested_graduation_year ?? null,
        suggested_class_letter: extras?.suggested_class_letter ?? null,
      })
    ).data,
  pending: async (): Promise<SuggestionGroup[]> =>
    (await api.get<SuggestionGroup[]>("/suggestions/pending")).data,
  pendingByTarget: async (): Promise<TargetWithSuggestions[]> =>
    (await api.get<TargetWithSuggestions[]>("/suggestions/pending/by-target")).data,
  byPerson: async (person_id: string): Promise<SuggestionGroup[]> =>
    (await api.get<SuggestionGroup[]>(`/suggestions/by-person/${person_id}`)).data,
  approve: async (
    suggestion_id: string,
    overrides?: {
      final_name?: string;
      final_graduation_year?: number | null;
      final_class_letter?: string | null;
    },
  ) => {
    await api.post(`/suggestions/${suggestion_id}/approve`, {
      final_name: overrides?.final_name ?? null,
      final_graduation_year: overrides?.final_graduation_year ?? null,
      final_class_letter: overrides?.final_class_letter ?? null,
    });
  },
  reject: async (suggestion_id: string) => {
    await api.post(`/suggestions/${suggestion_id}/reject`);
  },
  count: async (target: { person_id?: string; face_id?: string }): Promise<{ pending: number }> =>
    (await api.get("/suggestions/count", { params: target })).data,
};
