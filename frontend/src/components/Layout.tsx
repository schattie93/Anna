import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth, useUser } from "../auth";

export default function Layout() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();

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
          <NavLink to="/patienten">Patienten</NavLink>
          <NavLink to="/einstellungen">{user.full_name}</NavLink>
          <button className="link" onClick={logout}>
            Abmelden
          </button>
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
