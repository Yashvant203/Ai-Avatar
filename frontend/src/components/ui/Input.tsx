import { cn } from "@/lib/cn";

type Props = React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: Props) {
  return (
    <input
      className={cn(
        "h-11 w-full border-3 border-ink bg-paper px-3 font-mono text-sm rounded-brut",
        "placeholder:text-ink/40 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brut-blue",
        "shadow-brut-press focus:shadow-brut transition-shadow",
        className,
      )}
      {...props}
    />
  );
}
