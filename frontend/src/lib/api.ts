/** Thin API client. Feature calls (auth, avatars, generation) build on this in later phases. */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // Spread init first, then set merged headers last so init.headers (e.g. an
  // Authorization header added by authFetch) never clobbers Content-Type.
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, detail || res.statusText);
  }
  // 204 No Content (e.g. DELETE) and empty bodies have no JSON to parse.
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export interface HealthResponse {
  status: string;
  version: string;
  db: string;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/healthcheck");
}
