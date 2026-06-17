"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/Feedback";
import { Input } from "@/components/ui/Input";
import { Panel } from "@/components/ui/Panel";
import { useAuth } from "@/context/AuthProvider";
import { ApiError } from "@/lib/api";

type Mode = "login" | "signup";

const COPY: Record<
  Mode,
  { title: string; subtitle: string; cta: string; alt: string; altHref: string; altText: string }
> = {
  login: {
    title: "Welcome back",
    subtitle: "Log in to your AI Avatar account.",
    cta: "Log in",
    alt: "No account?",
    altHref: "/signup",
    altText: "Sign up",
  },
  signup: {
    title: "Create your account",
    subtitle: "Start building talking-head avatars in minutes.",
    cta: "Create account",
    alt: "Already have an account?",
    altHref: "/login",
    altText: "Log in",
  },
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block font-mono text-xs font-bold uppercase text-ink">{label}</span>
      {children}
    </label>
  );
}

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const { login, signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const copy = COPY[mode];

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "signup") await signup(email, password, fullName || undefined);
      else await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError)
        setError(err.status === 401 ? "Invalid email or password." : err.message);
      else setError("Something went wrong. Is the API running?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="mb-7 text-center">
        <Link href="/" className="inline-flex items-center gap-2 no-underline">
          <span className="grid h-8 w-8 place-items-center border-3 border-ink bg-paper text-sm text-ink">
            A
          </span>
          <span className="font-mono text-sm font-bold uppercase text-ink">AI Avatar</span>
        </Link>
        <h1 className="mt-6 text-2xl">{copy.title}</h1>
        <p className="mt-1.5 font-mono text-sm text-ink/70">{copy.subtitle}</p>
      </div>

      <Panel color="paper">
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {mode === "signup" && (
            <Field label="Name">
              <Input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Ada Lovelace"
                autoComplete="name"
              />
            </Field>
          )}
          <Field label="Email">
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
            />
          </Field>

          {error && <ErrorBanner message={error} />}

          <Button type="submit" color="blue" size="lg" className="w-full" disabled={busy}>
            {busy ? "Please wait…" : copy.cta}
          </Button>
        </form>
      </Panel>

      <p className="mt-5 text-center font-mono text-sm text-ink/70">
        {copy.alt}{" "}
        <Link href={copy.altHref} className="font-bold text-brut-blue no-underline">
          {copy.altText}
        </Link>
      </p>
    </div>
  );
}
