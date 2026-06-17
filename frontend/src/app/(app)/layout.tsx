import { AppShell } from "@/components/AppShell";
import { RequireAuth } from "@/components/auth/RequireAuth";

/** Authenticated area: guards access and renders the neo-brutalist app shell. */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
