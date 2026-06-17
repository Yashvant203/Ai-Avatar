"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AvatarCard } from "@/components/avatar/AvatarCard";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorBanner, Skeleton } from "@/components/ui/Feedback";
import { api } from "@/lib/apiClient";
import type { Avatar } from "@/lib/types";

export default function AvatarsPage() {
  const [avatars, setAvatars] = useState<Avatar[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listAvatars()
      .then(setAvatars)
      .catch((e) => setError(e.message ?? "Failed to load avatars"));
  }, []);

  useEffect(load, [load]);

  async function onDelete(id: number) {
    if (!confirm("Delete this avatar and its files?")) return;
    setError(null);
    try {
      await api.deleteAvatar(id);
      setAvatars((cur) => cur?.filter((a) => a.id !== id) ?? null);
    } catch (e) {
      setError((e as Error).message ?? "Delete failed");
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl">Your avatars</h1>
          <p className="mt-1 font-sans text-sm text-ink/70">
            Reusable talking-head profiles built from your videos.
          </p>
        </div>
        <Link href="/avatars/new">
          <Button color="blue">New avatar</Button>
        </Link>
      </header>

      {error && <ErrorBanner message={error} />}

      {!avatars ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-72" />
          ))}
        </div>
      ) : avatars.length === 0 ? (
        <EmptyState
          title="No avatars yet"
          hint="Record a short video and we'll build your reusable avatar."
          action={
            <Link href="/avatars/new">
              <Button color="blue">Create your first avatar</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {avatars.map((a) => (
            <AvatarCard key={a.id} avatar={a} onDelete={onDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
