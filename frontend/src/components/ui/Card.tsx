import { cn } from "@/lib/cn";

type Props = React.HTMLAttributes<HTMLDivElement>;

export function Card({ className, ...props }: Props) {
  return (
    <div
      className={cn("border-3 border-ink bg-paper rounded-brut shadow-brut p-6", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-lg mb-2", className)} {...props} />;
}
