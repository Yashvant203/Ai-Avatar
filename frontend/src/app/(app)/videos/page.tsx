"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { VideoCard } from "@/components/video/VideoCard";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorBanner, Skeleton } from "@/components/ui/Feedback";
import { api } from "@/lib/apiClient";
import type { GeneratedVideo } from "@/lib/types";

export default function VideosPage() {
  const [videos, setVideos] = useState<GeneratedVideo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listVideos()
      .then(setVideos)
      .catch((e) => setError(e.message ?? "Failed to load videos"));
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-3xl">Your videos</h1>
        <p className="mt-1 font-sans text-sm text-ink/70">
          Download or preview your generated MP4s.
        </p>
      </header>
      {error && <ErrorBanner message={error} />}

      {!videos ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      ) : videos.length === 0 ? (
        <EmptyState
          title="No videos yet"
          hint="Generate a video from one of your avatars."
          action={
            <Link href="/generate">
              <Button color="blue">Generate a video</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {videos.map((v) => (
            <VideoCard key={v.id} video={v} />
          ))}
        </div>
      )}
    </div>
  );
}
