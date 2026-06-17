"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { JobProgress } from "@/components/generate/JobProgress";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorBanner, Loading } from "@/components/ui/Feedback";
import { Panel } from "@/components/ui/Panel";
import { Textarea } from "@/components/ui/Textarea";
import { api } from "@/lib/apiClient";
import type { Avatar } from "@/lib/types";

function GenerateInner() {
  const params = useSearchParams();
  const preselect = params.get("avatar");

  const [avatars, setAvatars] = useState<Avatar[] | null>(null);
  const [avatarId, setAvatarId] = useState<number | null>(preselect ? Number(preselect) : null);
  const [script, setScript] = useState("");
  const [jobId, setJobId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listAvatars()
      .then((all) => {
        const ready = all.filter((a) => a.status === "ready");
        setAvatars(ready);
        if (avatarId == null && ready.length > 0) setAvatarId(ready[0].id);
      })
      .catch((e) => setError(e.message ?? "Failed to load avatars"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (avatarId == null || !script.trim()) return;
    setError(null);
    setBusy(true);
    try {
      const job = await api.generate(avatarId, script.trim());
      setJobId(job.job_id);
    } catch (e2) {
      setError((e2 as Error).message ?? "Could not start generation");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (jobId == null) return;
    try {
      await api.cancelJob(jobId);
    } catch {
      /* ignore — the poller will reflect the terminal state */
    }
  }

  if (avatars === null) return <Loading label="Loading avatars…" />;

  if (avatars.length === 0) {
    return (
      <EmptyState
        title="No ready avatars"
        hint="You need a finished avatar before generating a video."
        action={
          <Link href="/avatars/new">
            <Button color="blue">Create an avatar</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-3xl">Generate a video</h1>
        <p className="mt-1 font-sans text-sm text-ink/70">
          Pick an avatar and type any script.
        </p>
      </header>
      {error && <ErrorBanner message={error} />}

      {jobId == null ? (
        <Panel color="yellow">
          <form onSubmit={submit} className="space-y-5">
            <label className="block">
              <span className="mb-1.5 block font-mono text-xs font-bold uppercase text-ink">
                Avatar
              </span>
              <select
                value={avatarId ?? ""}
                onChange={(e) => setAvatarId(Number(e.target.value))}
                className="h-11 w-full border-3 border-ink bg-paper px-3 font-mono text-sm rounded-brut shadow-brut-press focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brut-blue"
              >
                {avatars.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1.5 block font-mono text-xs font-bold uppercase text-ink">
                Script
              </span>
              <Textarea
                required
                rows={8}
                maxLength={5000}
                value={script}
                onChange={(e) => setScript(e.target.value)}
                placeholder="Type anything you want your avatar to say…"
              />
              <span className="mt-1 block text-right font-mono text-xs text-ink/70">
                {script.length}/5000
              </span>
            </label>

            <Button type="submit" color="blue" size="lg" disabled={busy || !script.trim()}>
              {busy ? "Submitting…" : "Generate"}
            </Button>
          </form>
        </Panel>
      ) : (
        <div className="space-y-4">
          <JobProgress jobId={jobId} onCancel={cancel} />
          <Button color="yellow" onClick={() => setJobId(null)}>
            Start another
          </Button>
        </div>
      )}
    </div>
  );
}

export default function GeneratePage() {
  return (
    <Suspense fallback={<Loading />}>
      <GenerateInner />
    </Suspense>
  );
}
