import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const badge = cva(
  "inline-flex items-center border-3 border-ink rounded-brut px-2 py-0.5 " +
    "font-mono text-xs font-bold uppercase tracking-wide",
  {
    variants: {
      color: {
        yellow: "bg-brut-yellow text-ink",
        green: "bg-brut-green text-ink",
        pink: "bg-brut-pink text-ink",
        blue: "bg-brut-blue text-paper",
        lilac: "bg-brut-lilac text-ink",
        red: "bg-brut-red text-paper",
      },
    },
    defaultVariants: { color: "lilac" },
  },
);

type Props = React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>;

export function Badge({ color, className, ...props }: Props) {
  return <span className={cn(badge({ color }), className)} {...props} />;
}
