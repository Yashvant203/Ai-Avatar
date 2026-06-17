// TS types mirroring the backend Pydantic schemas.

export type AvatarStatus = "pending" | "processing" | "ready" | "failed";
export type VideoStatus = "uploaded" | "processing" | "analyzed" | "failed";
export type VoiceStatus = "pending" | "training" | "ready" | "failed";
export type JobStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";

export interface Avatar {
  id: number;
  name: string;
  status: AvatarStatus;
  profile_path: string | null;
  thumbnail_path: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface Script {
  id: number;
  avatar_id: number | null;
  content: string;
  word_count: number;
  language: string;
  created_at: string;
}

export interface TrainingVideoInfo {
  id: number;
  status: VideoStatus;
  duration_seconds: number | null;
  resolution: string | null;
  created_at: string;
}

export interface VoiceModelInfo {
  id: number;
  status: VoiceStatus;
  sample_rate: number;
}

export interface AvatarStatusInfo {
  avatar_id: number;
  status: AvatarStatus;
  error_message: string | null;
  video: TrainingVideoInfo | null;
  voice_model: VoiceModelInfo | null;
}

export interface JobCreated {
  job_id: number;
  status: JobStatus;
  estimated_duration_s: number;
}

export interface Job {
  id: number;
  avatar_id: number;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  output_video_id: number | null;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface GeneratedVideo {
  id: number;
  job_id: number;
  avatar_id: number;
  duration_seconds: number | null;
  resolution: string | null;
  file_size_bytes: number | null;
  created_at: string;
}

export const TERMINAL_JOB_STATES: JobStatus[] = ["completed", "failed", "cancelled"];
export const TERMINAL_AVATAR_STATES: AvatarStatus[] = ["ready", "failed"];
