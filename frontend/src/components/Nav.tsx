"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/context/AuthProvider";

// Landing top bar — neo-brutalism treatment.
export function Nav() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  function onLogout() {
    logout();
    router.push("/");
  }

  return (
    <nav className="flex items-center justify-between gap-4 border-b-3 border-ink pb-4 pt-4">
      <Link
        href="/"
        className="flex items-center gap-2 font-mono text-sm font-bold uppercase text-ink no-underline"
      >
        <span className="grid h-7 w-7 place-items-center border-3 border-ink bg-paper text-sm">
          A
        </span>
        AI&nbsp;Avatar
      </Link>

      <div className="flex items-center gap-2">
        {loading ? null : user ? (
          <>
            <Link href="/dashboard">
              <Button color="yellow" size="md">
                Dashboard
              </Button>
            </Link>
            <Button color="yellow" size="md" onClick={onLogout}>
              Log out
            </Button>
          </>
        ) : (
          <>
            <Link href="/login">
              <Button color="yellow" size="md">
                Log in
              </Button>
            </Link>
            <Link href="/signup">
              <Button color="blue" size="md">
                Start for free
              </Button>
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
