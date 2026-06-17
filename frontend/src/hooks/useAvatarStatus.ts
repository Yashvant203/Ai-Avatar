"use client";

import { useCallback } from "react";

import { api } from "@/lib/apiClient";
import { TERMINAL_AVATAR_STATES, type AvatarStatusInfo } from "@/lib/types";

import { usePolling } from "./usePolling";

/** Poll an avatar's creation status until ready/failed. */
export function useAvatarStatus(avatarId: number | null, enabled = true) {
  const fetcher = useCallback(() => {
    if (avatarId == null) return Promise.reject(new Error("no avatar"));
    return api.getAvatarStatus(avatarId);
  }, [avatarId]);

  return usePolling<AvatarStatusInfo>({
    fetcher,
    enabled: enabled && avatarId != null,
    isDone: (s) => TERMINAL_AVATAR_STATES.includes(s.status),
  });
}
