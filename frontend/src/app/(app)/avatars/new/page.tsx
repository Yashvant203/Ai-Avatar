"use client";

import Link from "next/link";
import { useState } from "react";

import { Recorder } from "@/components/avatar/Recorder";
import { ScriptDisplay } from "@/components/avatar/ScriptDisplay";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Input";
import { Panel } from "@/components/ui/Panel";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAvatarStatus } from "@/hooks/useAvatarStatus";
import { api, uploadTrainingVideo } from "@/lib/apiClient";
import type { Avatar, Script } from "@/lib/types";

type Step = "name" | "record" | "processing";

const STEP_LABELS = ["Name", "Record", "Process"];

export default function NewAvatarPage() {
  const [step, setStep] = useState<Step>("name");
  const [name, setName] = useState("");
  const [avatar, setAvatar] = useState<Avatar | null>(null);
  const [script, setScript] = useState<Script | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createAndScript(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const a = await api.createAvatar(name.trim());
      const s = await api.generateScript(a.id);
      setAvatar(a);
      setScript(s);
      setStep("record");
    } catch (e2) {
      setError((e2 as Error).message ?? "Could not create avatar");
    } finally {
      setBusy(false);
    }
  }

  async function startProcessing() {
    if (!avatar || !file) return;
    setError(null);
    setBusy(true);
    setUploadPct(0);
    try {
      await uploadTrainingVideo(avatar.id, file, setUploadPct);
      setStep("processing");
    } catch (e) {
      setError((e as Error).message ?? "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl">Create an avatar</h1>
          <p className="mt-1 font-sans text-sm text-ink/70">Three steps: name, record, process.</p>
        </div>
      </header>
      <Stepper step={step} />
      {error && <ErrorBanner message={error} />}

      {step === "name" && (
        <Panel color="yellow">
          <h1 className="mb-4 text-2xl">Name your avatar</h1>
          <form onSubmit={createAndScript} className="space-y-4">
            <Input
              autoFocus
              required
              maxLength={255}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Work Presenter"
            />
            <Button type="submit" color="blue" size="lg" disabled={busy || !name.trim()}>
              {busy ? "Generating script…" : "Continue"}
            </Button>
          </form>
        </Panel>
      )}

      {step === "record" && script && (
        <div className="space-y-6">
          <ScriptDisplay script={script} />
          <Recorder onReady={setFile} />
          <Button color="blue" size="lg" disabled={!file || busy} onClick={startProcessing}>
            {busy && uploadPct !== null ? `Uploading ${uploadPct}%` : "Start processing"}
          </Button>
          {uploadPct !== null && busy && <ProgressBar value={uploadPct} />}
        </div>
      )}

      {step === "processing" && avatar && <Processing avatarId={avatar.id} />}
    </div>
  );
}

function Stepper({ step }: { step: Step }) {
  const idx = { name: 0, record: 1, processing: 2 }[step];
  return (
    <div className="flex gap-2">
      {STEP_LABELS.map((label, i) => (
        <div
          key={label}
          className={`flex-1 border-3 border-ink px-3 py-2 text-center font-mono text-xs font-bold uppercase ${
            i <= idx ? "bg-ink text-paper" : "bg-paper"
          }`}
        >
          {i + 1}. {label}
        </div>
      ))}
    </div>
  );
}

const PCT: Record<string, number> = { uploaded: 25, processing: 65, analyzed: 100 };

function Processing({ avatarId }: { avatarId: number }) {
  const { data, error } = useAvatarStatus(avatarId);
  const status = data?.status;
  const videoStatus = data?.video?.status;
  const pct = status === "ready" ? 100 : (PCT[videoStatus ?? "uploaded"] ?? 10);

  return (
    <Panel color="paper" className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl">Building your avatar</h1>
        {status && <StatusBadge status={status} />}
      </div>

      {error && <ErrorBanner message="Lost connection while polling. Retrying…" />}

      {status === "failed" ? (
        <ErrorBanner message={`Processing failed: ${data?.error_message ?? "unknown error"}`} />
      ) : status === "ready" ? (
        <div className="space-y-4">
          <ProgressBar value={100} />
          <p className="font-mono text-sm font-bold uppercase text-brut-green">
            ✓ Avatar ready — your voice and face are cloned.
          </p>
          <div className="flex gap-3">
            <Link href={`/generate?avatar=${avatarId}`}>
              <Button color="blue" size="lg">
                Generate a video
              </Button>
            </Link>
            <Link href="/avatars">
              <Button color="yellow" size="lg">
                My avatars
              </Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <ProgressBar value={pct} />
          <p className="animate-pulse font-mono text-sm uppercase text-ink/70">
            Analyzing face, voice, expressions &amp; head movement… this can take a while.
          </p>
        </div>
      )}
    </Panel>
  );
}
