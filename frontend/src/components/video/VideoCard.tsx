"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { downloadVideo, fetchVideoBlob } from "@/lib/apiClient";
import type { GeneratedVideo } from "@/lib/types";

function fmtSize(bytes: number | null): string {
  if (!bytes) return "—";
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function VideoCard({ video }: { video: GeneratedVideo }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "download" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function preview() {
    setError(null);
    setBusy("preview");
    try {
      const blob = await fetchVideoBlob(video.id);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch {
      setError("Could not load preview");
    } finally {
      setBusy(null);
    }
  }

  async function download() {
    setError(null);
    setBusy("download");
    try {
      await downloadVideo(video.id, `avatar_${video.avatar_id}_video_${video.id}.mp4`);
    } catch {
      setError("Download failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="aspect-video w-full overflow-hidden border-3 border-ink bg-ink rounded-brut shadow-brut">
        {previewUrl ? (
          <video src={previewUrl} controls className="h-full w-full" />
        ) : (
          <button
            onClick={preview}
            disabled={busy === "preview"}
            className="flex h-full w-full items-center justify-center font-mono text-sm font-bold uppercase text-paper hover:bg-ink/90"
          >
            {busy === "preview" ? "Loading…" : "▶ Preview"}
          </button>
        )}
      </div>

      <div className="font-mono text-xs text-ink/70">
        Video #{video.id} · {video.resolution ?? "—"} · {fmtSize(video.file_size_bytes)}
      </div>

      {error && <p className="font-mono text-xs font-bold text-brut-red">{error}</p>}

      <Button
        color="blue"
        className="w-full"
        disabled={busy === "download"}
        onClick={download}
      >
        {busy === "download" ? "Downloading…" : "⬇ Download MP4"}
      </Button>
    </Card>
  );
}
