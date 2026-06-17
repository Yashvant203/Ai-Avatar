"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { Avatar } from "@/lib/types";

export function AvatarCard({
  avatar,
  onDelete,
}: {
  avatar: Avatar;
  onDelete: (id: number) => void;
}) {
  const ready = avatar.status === "ready";
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-lg">{avatar.name}</h3>
        <StatusBadge status={avatar.status} />
      </div>

      {/* Thumbnail placeholder block (files are auth-protected; served later). */}
      <div className="grid aspect-square place-items-center border-3 border-ink bg-brut-lilac rounded-brut">
        <span className="font-mono text-3xl font-bold text-ink">
          {avatar.name.slice(0, 1).toUpperCase()}
        </span>
      </div>

      {avatar.status === "failed" && avatar.error_message && (
        <p className="font-mono text-xs font-bold text-brut-red">{avatar.error_message}</p>
      )}

      <div className="mt-auto flex gap-2">
        {ready && (
          <Link href={`/generate?avatar=${avatar.id}`} className="flex-1">
            <Button color="blue" className="w-full">
              Generate
            </Button>
          </Link>
        )}
        <Button color="pink" onClick={() => onDelete(avatar.id)}>
          Delete
        </Button>
      </div>
    </Card>
  );
}
