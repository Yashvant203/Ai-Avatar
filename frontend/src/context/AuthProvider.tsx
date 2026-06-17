"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import * as auth from "@/lib/auth";
import type { UserOut } from "@/lib/auth";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount, if a token exists, hydrate the current user.
  useEffect(() => {
    let active = true;
    if (!auth.isAuthenticated()) {
      setLoading(false);
      return;
    }
    auth
      .fetchMe()
      .then((u) => active && setUser(u))
      .catch(() => active && setUser(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await auth.login({ email, password });
    auth.setTokens(tokens);
    setUser(await auth.fetchMe());
  }, []);

  const signup = useCallback(async (email: string, password: string, fullName?: string) => {
    const tokens = await auth.signup({ email, password, full_name: fullName });
    auth.setTokens(tokens);
    setUser(await auth.fetchMe());
  }, []);

  const logout = useCallback(() => {
    auth.clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, signup, logout }),
    [user, loading, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
