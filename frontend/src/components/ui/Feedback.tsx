import { cn } from "@/lib/cn";

/** Hard-shadow error banner. */
export function ErrorBanner({ message, className }: { message: string; className?: string }) {
  return (
    <div
      role="alert"
      className={cn(
        "border-3 border-ink bg-brut-red px-4 py-3 font-mono text-sm font-bold text-paper shadow-brut",
        className,
      )}
    >
      {message}
    </div>
  );
}

/** Bordered placeholder block used as a loading skeleton. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse border-3 border-ink bg-ink/10", className)} />;
}

/** Illustrative empty-state panel. */
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="border-3 border-dashed border-ink bg-paper p-10 text-center shadow-brut">
      <p className="font-mono text-lg font-bold uppercase">{title}</p>
      {hint && <p className="mt-2 font-sans text-sm text-ink/70">{hint}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

/** Small monospace loading indicator. */
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="animate-pulse font-mono text-sm uppercase tracking-wide text-ink/70">{label}</p>
  );
}
