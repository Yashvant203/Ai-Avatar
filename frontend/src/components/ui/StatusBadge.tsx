import { Badge } from "@/components/ui/Badge";
import type { AvatarStatus, JobStatus } from "@/lib/types";

type AnyStatus = AvatarStatus | JobStatus;

const COLOR: Record<AnyStatus, "yellow" | "blue" | "green" | "red" | "lilac"> = {
  pending: "lilac",
  queued: "lilac",
  processing: "blue",
  ready: "green",
  completed: "green",
  failed: "red",
  cancelled: "red",
};

export function StatusBadge({ status }: { status: AnyStatus }) {
  return <Badge color={COLOR[status] ?? "lilac"}>{status}</Badge>;
}
