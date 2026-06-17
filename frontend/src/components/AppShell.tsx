"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/context/AuthProvider";
import { cn } from "@/lib/cn";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/avatars", label: "Avatars" },
  { href: "/avatars/new", label: "Create avatar" },
  { href: "/generate", label: "Generate" },
  { href: "/videos", label: "Videos" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  function onLogout() {
    logout();
    router.push("/");
  }

  return (
    <div className="min-h-screen">
      <header className="border-b-5 border-ink bg-brut-yellow">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3 px-6 py-3 md:px-10">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 font-mono text-sm font-bold uppercase text-ink no-underline"
          >
            <span className="grid h-7 w-7 place-items-center border-3 border-ink bg-paper text-sm">
              A
            </span>
            AI&nbsp;Avatar
          </Link>

          <nav className="flex flex-1 flex-wrap gap-2">
            {LINKS.map((l) => {
              const active = pathname === l.href;
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={cn(
                    "shrink-0 border-3 border-ink px-3 py-2 font-mono text-sm font-bold uppercase no-underline",
                    active
                      ? "bg-ink text-paper shadow-brut-press"
                      : "bg-paper shadow-brut hover:translate-x-0.5 hover:translate-y-0.5 hover:shadow-brut-press",
                  )}
                >
                  {l.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-3">
            {user && (
              <p className="hidden truncate font-mono text-xs text-ink/70 sm:block">{user.email}</p>
            )}
            <Button color="pink" size="md" onClick={onLogout}>
              Log out
            </Button>
          </div>
        </div>
      </header>

      <main className="p-6 md:p-10">{children}</main>
    </div>
  );
}
