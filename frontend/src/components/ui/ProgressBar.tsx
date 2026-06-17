import { cn } from "@/lib/cn";

/** Chunky bordered progress bar with a hard-edged fill. */
export function ProgressBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn("h-6 w-full border-3 border-ink bg-paper", className)}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full bg-brut-green transition-[width] duration-300"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
