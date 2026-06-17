"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorBanner, Skeleton } from "@/components/ui/Feedback";
import { Panel } from "@/components/ui/Panel";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/context/AuthProvider";
import { api } from "@/lib/apiClient";
import type { Avatar, GeneratedVideo, Job } from "@/lib/types";

function Stat({ label, value, href }: { label: string; value: number; href: string }) {
  return (
    <Link href={href} className="no-underline">
      <Card>
        <span className="font-mono text-3xl font-bold">{value}</span>
        <p className="mt-1 font-mono text-xs uppercase text-ink/70">{label}</p>
      </Card>
    </Link>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<{ avatars: Avatar[]; jobs: Job[]; videos: GeneratedVideo[] }>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listAvatars(), api.listJobs(), api.listVideos()])
      .then(([avatars, jobs, videos]) => setData({ avatars, jobs, videos }))
      .catch((e) => setError(e.message ?? "Failed to load dashboard"));
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-7">
      {/* Welcome hero */}
      <Panel color="yellow">
        <p className="font-mono text-sm font-bold uppercase text-ink/70">welcome back</p>
        <h1 className="mt-1 text-3xl sm:text-4xl">
          {user?.full_name || user?.email?.split("@")[0] || "Creator"}
        </h1>
        <p className="mt-2 font-mono text-sm text-ink/70">{user?.email}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/avatars/new">
            <Button color="blue" size="lg">
              Create avatar
            </Button>
          </Link>
          <Link href="/generate">
            <Button color="green" size="lg">
              Generate video
            </Button>
          </Link>
        </div>
      </Panel>

      {error && <ErrorBanner message={error} />}

      {/* Stats */}
      <section className="grid gap-4 sm:grid-cols-3">
        {data ? (
          <>
            <Stat label="Avatars" value={data.avatars.length} href="/avatars" />
            <Stat label="Jobs" value={data.jobs.length} href="/generate" />
            <Stat label="Videos" value={data.videos.length} href="/videos" />
          </>
        ) : (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-[88px]" />)
        )}
      </section>

      {/* Recent activity */}
      <section>
        <h2 className="mb-3 text-lg">Recent jobs</h2>
        {!data ? (
          <Skeleton className="h-24" />
        ) : data.jobs.length === 0 ? (
          <EmptyState
            title="No jobs yet"
            hint="Generate your first video to see it here."
            action={
              <Link href="/generate">
                <Button color="blue">Generate video</Button>
              </Link>
            }
          />
        ) : (
          <div className="space-y-3">
            {data.jobs.slice(0, 5).map((j) => (
              <Card key={j.id} className="flex items-center justify-between gap-4">
                <span className="font-mono text-sm text-ink/70">
                  <span className="text-ink">Job #{j.id}</span> · avatar {j.avatar_id} ·{" "}
                  {j.progress}%
                </span>
                <StatusBadge status={j.status} />
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
