// Typed API client built on the auth-aware fetch wrapper (lib/auth.ts).

import { API_BASE_URL, ApiError } from "@/lib/api";
import { authFetch, getAccessToken } from "@/lib/auth";
import type {
  Avatar,
  AvatarStatusInfo,
  GeneratedVideo,
  Job,
  JobCreated,
  Script,
} from "@/lib/types";

export const api = {
  // --- Avatars -------------------------------------------------------------
  listAvatars: () => authFetch<Avatar[]>("/api/avatars"),
  getAvatar: (id: number) => authFetch<Avatar>(`/api/avatars/${id}`),
  createAvatar: (name: string) =>
    authFetch<Avatar>("/api/avatars", { method: "POST", body: JSON.stringify({ name }) }),
  deleteAvatar: (id: number) => authFetch<void>(`/api/avatars/${id}`, { method: "DELETE" }),
  generateScript: (id: number) =>
    authFetch<Script>(`/api/avatars/${id}/script`, { method: "POST" }),
  getScript: (id: number) => authFetch<Script>(`/api/avatars/${id}/script`),
  getAvatarStatus: (id: number) => authFetch<AvatarStatusInfo>(`/api/avatars/${id}/status`),

  // --- Generation ----------------------------------------------------------
  generate: (avatarId: number, scriptText: string) =>
    authFetch<JobCreated>("/api/generate", {
      method: "POST",
      body: JSON.stringify({ avatar_id: avatarId, script_text: scriptText }),
    }),
  listJobs: () => authFetch<Job[]>("/api/jobs"),
  getJob: (id: number) => authFetch<Job>(`/api/jobs/${id}`),
  cancelJob: (id: number) => authFetch<Job>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  listVideos: () => authFetch<GeneratedVideo[]>("/api/videos"),
};

/**
 * Upload a training video with progress. Uses XHR (fetch lacks upload-progress
 * events). Multipart Content-Type is set by the browser (with boundary).
 */
export function uploadTrainingVideo(
  avatarId: number,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/avatars/${avatarId}/video`);
    const token = getAccessToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new ApiError(xhr.status, xhr.responseText || xhr.statusText));
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error during upload"));
    xhr.send(form);
  });
}

/** Fetch a generated video as a blob (auth-protected) for preview/download. */
export async function fetchVideoBlob(videoId: number): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/api/videos/${videoId}/download`, {
    headers: { Authorization: `Bearer ${getAccessToken() ?? ""}` },
  });
  if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => res.statusText));
  return res.blob();
}

/** Trigger a browser download of a generated video. */
export async function downloadVideo(videoId: number, filename: string): Promise<void> {
  const blob = await fetchVideoBlob(videoId);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
