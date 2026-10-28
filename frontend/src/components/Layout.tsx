import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth, useUser } from "../auth";

export default function Layout() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const online = useServerReachable();

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
      {!online && (
        <div className="offline-banner" role="alert">
          Keine Verbindung zum Praxisserver – Änderungen werden erst nach Wiederverbindung gespeichert. Bitte WLAN prüfen; offene Formulare bleiben auf dem Bildschirm erhalten.
        </div>
      )}
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

/** Prüft regelmäßig, ob der Praxisserver erreichbar ist (z. B. WLAN-Ausfall am Tablet). */
function useServerReachable(): boolean {
  const [ok, setOk] = useState(true);
  useEffect(() => {
    let alive = true;
    const ping = () =>
      fetch("/api/health", { cache: "no-store" }).then(
        (r) => alive && setOk(r.ok),
        () => alive && setOk(false),
      );
    const timer = setInterval(ping, 15000);
    window.addEventListener("online", ping);
    window.addEventListener("offline", () => setOk(false));
    return () => {
      alive = false;
      clearInterval(timer);
      window.removeEventListener("online", ping);
    };
  }, []);
  return ok;
}
