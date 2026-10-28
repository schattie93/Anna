import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type AuthStatus, type User } from "./api";

interface AuthState {
  status: AuthStatus | null;
  setUser: (u: User | null) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);

  useEffect(() => {
    api<AuthStatus>("/auth/status").then(setStatus, () => setStatus({ setup_required: false, user: null }));
    const onUnauthorized = () => setStatus((s) => (s ? { ...s, user: null } : s));
    window.addEventListener("physioflow:unauthorized", onUnauthorized);
    return () => window.removeEventListener("physioflow:unauthorized", onUnauthorized);
  }, []);

  const setUser = useCallback((user: User | null) => setStatus({ setup_required: false, user }), []);
  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
  }, [setUser]);

  return <AuthContext.Provider value={{ status, setUser, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth außerhalb von AuthProvider");
  return ctx;
}

export function useUser(): User {
  const user = useAuth().status?.user;
  if (!user) throw new Error("Nicht angemeldet");
  return user;
}
