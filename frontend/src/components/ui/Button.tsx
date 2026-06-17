"use client";

import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const button = cva(
  "inline-flex items-center justify-center font-mono font-bold uppercase tracking-wide " +
    "border-3 border-ink rounded-brut shadow-brut " +
    "transition-all duration-75 active:translate-x-1 active:translate-y-1 active:shadow-brut-press " +
    "disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none " +
    "focus-visible:ring-4 focus-visible:ring-brut-blue",
  {
    variants: {
      color: {
        yellow: "bg-brut-yellow text-ink",
        pink: "bg-brut-pink text-ink",
        blue: "bg-brut-blue text-paper",
        green: "bg-brut-green text-ink",
      },
      size: { md: "h-11 px-5 text-sm", lg: "h-14 px-8 text-base" },
    },
    defaultVariants: { color: "yellow", size: "md" },
  },
);

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button>;

export function Button({ color, size, className, ...props }: Props) {
  return <button className={cn(button({ color, size }), className)} {...props} />;
}
