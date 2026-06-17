import { cn } from "@/lib/cn";

type Props = React.HTMLAttributes<HTMLDivElement> & {
  color?: "yellow" | "pink" | "blue" | "green" | "lilac" | "paper";
};

const bg: Record<NonNullable<Props["color"]>, string> = {
  yellow: "bg-brut-yellow",
  pink: "bg-brut-pink",
  blue: "bg-brut-blue text-paper",
  green: "bg-brut-green",
  lilac: "bg-brut-lilac",
  paper: "bg-paper",
};

/** A bold, full-bleed colored block with the heavy border + offset shadow. */
export function Panel({ color = "paper", className, ...props }: Props) {
  return (
    <div
      className={cn("border-5 border-ink rounded-brut shadow-brut-lg p-8", bg[color], className)}
      {...props}
    />
  );
}
