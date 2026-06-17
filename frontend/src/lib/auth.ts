/**
 * Token storage + auth-aware fetch.
 *
 * SECURITY TRADEOFF: tokens are kept in localStorage so the SPA can attach a
 * Bearer header to API calls. localStorage is readable by any script on the
 * page, so an XSS bug could exfiltrate tokens. We accept this for the MVP and
 * mitigate with (a) a short access-token TTL (15 min) and (b) refresh-token
 * rotation on every refresh. The hardened path is httpOnly, SameSite cookies
 * set by the backend — see docs/IMPLEMENTATION_ROADMAP.md (Phase 2 risks).
 */

import { apiFetch, ApiError } from "@/lib/api";

const ACCESS_KEY = "aap.access";
const REFRESH_KEY = "aap.refresh";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserOut {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

const isBrowser = typeof window !== "undefined";

export function getAccessToken(): string | null {
  return isBrowser ? window.localStorage.getItem(ACCESS_KEY) : null;
}

export function getRefreshToken(): string | null {
  return isBrowser ? window.localStorage.getItem(REFRESH_KEY) : null;
}

export function setTokens(tokens: TokenPair): void {
  if (!isBrowser) return;
  window.localStorage.setItem(ACCESS_KEY, tokens.access_token);
  window.localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  if (!isBrowser) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

// --- Auth API calls --------------------------------------------------------
export function signup(input: {
  email: string;
  password: string;
  full_name?: string;
}): Promise<TokenPair> {
  return apiFetch<TokenPair>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function login(input: { email: string; password: string }): Promise<TokenPair> {
  return apiFetch<TokenPair>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

async function refresh(): Promise<TokenPair | null> {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return null;
  try {
    const tokens = await apiFetch<TokenPair>("/api/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    });
    setTokens(tokens);
    return tokens;
  } catch {
    clearTokens();
    return null;
  }
}

/**
 * Authenticated fetch: attaches the Bearer token and, on a 401, attempts a
 * single silent refresh + retry before giving up.
 */
export async function authFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const withAuth = (token: string | null): RequestInit => ({
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  try {
    return await apiFetch<T>(path, withAuth(getAccessToken()));
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      const rotated = await refresh();
      if (rotated) {
        return apiFetch<T>(path, withAuth(rotated.access_token));
      }
    }
    throw err;
  }
}

export function fetchMe(): Promise<UserOut> {
  return authFetch<UserOut>("/api/auth/me");
}
