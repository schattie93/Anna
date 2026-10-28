import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type AuthStatus, type User } from "./api";
import * as offline from "./offline/core";
import * as vault from "./offline/vault";

interface AuthState {
  status: AuthStatus | null;
  setUser: (u: User | null) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);

  useEffect(() => {
    api<AuthStatus>("/auth/status").then(
      (st) => {
        if (st.user) localStorage.setItem("physioflow_user", JSON.stringify(st.user));
        setStatus(st);
      },
      () => {
        // Kein Server erreichbar: mit dem zuletzt angemeldeten Benutzer offline weiterarbeiten (Daten bleiben verschlüsselt)
        try {
          const cached = JSON.parse(localStorage.getItem("physioflow_user") ?? "null") as User | null;
          setStatus({ setup_required: false, user: cached });
        } catch {
          setStatus({ setup_required: false, user: null });
        }
      },
    );
    const onUnauthorized = () => setStatus((s) => (s ? { ...s, user: null } : s));
    window.addEventListener("physioflow:unauthorized", onUnauthorized);
    return () => window.removeEventListener("physioflow:unauthorized", onUnauthorized);
  }, []);

  const setUser = useCallback((user: User | null) => {
    if (user) localStorage.setItem("physioflow_user", JSON.stringify(user));
    setStatus({ setup_required: false, user });
  }, []);
  const logout = useCallback(async () => {
    const pending = offline.getState().pending;
    if (pending > 0 && !window.confirm(`${pending} offline erfasste Einträge sind noch nicht übertragen. Sie bleiben verschlüsselt auf diesem Gerät und werden nach der nächsten Anmeldung übertragen. Trotzdem abmelden?`)) return;
    await api("/auth/logout", { method: "POST" });
    localStorage.removeItem("physioflow_user");
    vault.lock();
    setUser(null);
  }, [setUser]);

  useEffect(() => {
    const u = status?.user;
    offline.setUser(u ? { id: u.id, full_name: u.full_name } : null);
    if (status && !u) vault.lock();
  }, [status]);

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
