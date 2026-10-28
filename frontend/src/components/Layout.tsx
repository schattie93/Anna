import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth, useUser } from "../auth";
import * as core from "../offline/core";
import { OfflineBar, useOffline } from "../offline/OfflineUI";

export default function Layout() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();
  useOfflineBackground();

  // Tastaturkürzel für die PC-Bedienung
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement).closest("input, textarea, select, [contenteditable]");
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "/") {
        e.preventDefault();
        navigate("/patienten");
      } else if (e.key === "n") {
        navigate("/patienten/neu");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          PhysioFlow
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Übersicht
          </NavLink>
          <NavLink to="/termine">Termine</NavLink>
          <NavLink to="/patienten">Patienten</NavLink>
          {user.role !== "reception" && <NavLink to="/uebungen">Übungen</NavLink>}
          <NavLink to="/abrechnung">Abrechnung</NavLink>
          {user.role !== "reception" && <NavLink to="/auswertung">Auswertung</NavLink>}
          {user.role === "admin" && <NavLink to="/verwaltung">Verwaltung</NavLink>}
          <NavLink to="/einstellungen">{user.full_name}</NavLink>
          <button className="link" onClick={logout}>
            Abmelden
          </button>
        </nav>
      </header>
      <OfflineBar />
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

/** Hält Erreichbarkeit, Übertragung und Vorbereitung für die Offline-Nutzung im Hintergrund aktuell. */
function useOfflineBackground() {
  const s = useOffline();
  useEffect(() => {
    const ping = () =>
      fetch("/api/health", { cache: "no-store", signal: AbortSignal.timeout(8000) }).then(
        (r) => core.setReachable(r.ok),
        () => core.setReachable(false),
      );
    const timer = setInterval(() => {
      void ping();
      core.syncSoon();
    }, 15000);
    const up = () => void ping();
    const down = () => core.setReachable(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      clearInterval(timer);
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  // Akten der heutigen Patienten automatisch vorbereiten (höchstens alle 10 Minuten), solange entsperrt
  useEffect(() => {
    if (s.vault === "unlocked" && s.reachable && !s.preparing && (!s.lastPrepared || Date.now() - s.lastPrepared > 10 * 60_000)) void core.prepare();
  }, [s.vault, s.reachable, s.preparing, s.lastPrepared]);
}
