"use client";

import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/Feedback";
import { Panel } from "@/components/ui/Panel";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useJobStatus } from "@/hooks/useJobStatus";

// Progress → human stage label (mirrors the worker's progress bands).
function stageFor(progress: number): string {
  if (progress >= 85) return "Rendering video";
  if (progress >= 60) return "Lip-syncing (MuseTalk)";
  if (progress >= 30) return "Animating (LivePortrait)";
  if (progress >= 5) return "Synthesizing speech (F5-TTS)";
  return "Queued";
}

export function JobProgress({ jobId, onCancel }: { jobId: number; onCancel?: () => void }) {
  const { data: job, error } = useJobStatus(jobId);

  if (!job) {
    return (
      <Panel>
        <p className="animate-pulse font-mono text-sm text-ink/70">
          Starting <span className="text-ink">job #{jobId}</span>…
        </p>
      </Panel>
    );
  }

  return (
    <Panel className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-mono">Job #{job.id}</h2>
        <StatusBadge status={job.status} />
      </div>

      {error && <ErrorBanner message="Lost connection while polling. Retrying…" />}

      {job.status === "failed" ? (
        <ErrorBanner message={`Generation failed: ${job.error_message ?? "unknown error"}`} />
      ) : job.status === "cancelled" ? (
        <ErrorBanner message="Job cancelled." />
      ) : job.status === "completed" ? (
        <div className="space-y-4">
          <ProgressBar value={100} />
          <p className="font-mono text-sm font-bold uppercase text-brut-green">✓ Video ready.</p>
          <Link href="/videos">
            <Button color="blue" size="lg">
              Go to videos
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          <ProgressBar value={job.progress} />
          <div className="flex items-center justify-between font-mono text-sm">
            <span className="text-ink/70">{stageFor(job.progress)}</span>
            <span className="font-bold text-ink">{job.progress}%</span>
          </div>
          {onCancel && (
            <Button color="pink" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      )}
    </Panel>
  );
}
