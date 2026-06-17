import { cn } from "@/lib/cn";

type Props = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ className, ...props }: Props) {
  return (
    <textarea
      className={cn(
        "w-full border-3 border-ink bg-paper p-3 font-mono text-sm rounded-brut shadow-brut-press",
        "placeholder:text-ink/40 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brut-blue",
        "focus:shadow-brut transition-shadow",
        className,
      )}
      {...props}
    />
  );
}
