"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, name: string) => Promise<User>;
  logout: () => void;
  /** Re-read the signed-in user (e.g. after verifying the email address). */
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

// The session is an httpOnly cookie owned by the API; the browser sends it automatically. We never see or store
// a token, so "am I signed in?" is answered by asking the API.
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api<User>("/v1/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true));
  }, []);

  const finish = (r: { user: User }) => {
    setUser(r.user);
    return r.user;
  };

  const login = useCallback(
    async (email: string, password: string) =>
      finish(await api("/v1/auth/login", { method: "POST", json: { email, password } })),
    [],
  );

  const register = useCallback(
    async (email: string, password: string, name: string) =>
      finish(await api("/v1/auth/register", { method: "POST", json: { email, password, name } })),
    [],
  );

  const logout = useCallback(() => {
    setUser(null);
    // Revokes the session server-side (and clears the cookie), not just forgets it locally.
    api("/v1/auth/logout", { method: "POST" }).catch(() => {});
  }, []);

  const refresh = useCallback(async () => {
    setUser(await api<User>("/v1/auth/me").catch(() => null));
  }, []);

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout, refresh }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
