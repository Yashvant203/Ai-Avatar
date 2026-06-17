"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/context/AuthProvider";

/**
 * Client-side route guard. Redirects unauthenticated users to /login.
 *
 * Why not Next middleware? Tokens live in localStorage (see lib/auth.ts), which
 * is not readable in the edge/server middleware runtime. With an httpOnly-cookie
 * strategy this guard would move to middleware.ts instead.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center font-mono text-sm uppercase">
        Loading…
      </div>
    );
  }

  return <>{children}</>;
}
