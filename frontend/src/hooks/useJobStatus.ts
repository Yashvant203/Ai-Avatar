"use client";

import { useCallback } from "react";

import { api } from "@/lib/apiClient";
import { TERMINAL_JOB_STATES, type Job } from "@/lib/types";

import { usePolling } from "./usePolling";

/** Poll a generation job until it reaches a terminal state. */
export function useJobStatus(jobId: number | null) {
  const fetcher = useCallback(() => {
    if (jobId == null) return Promise.reject(new Error("no job"));
    return api.getJob(jobId);
  }, [jobId]);

  return usePolling<Job>({
    fetcher,
    enabled: jobId != null,
    isDone: (j) => TERMINAL_JOB_STATES.includes(j.status),
  });
}
