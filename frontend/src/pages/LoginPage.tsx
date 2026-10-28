import { useState, type FormEvent } from "react";
import { api, type User } from "../api";
import { useAuth } from "../auth";
import { ErrorBox, TextField } from "../components/fields";

export default function LoginPage({ setup }: { setup: boolean }) {
  const { setUser } = useAuth();
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = setup
        ? await api<User>("/auth/setup", { method: "POST", body: { username, full_name: fullName, password } })
        : await api<User>("/auth/login", { method: "POST", body: { username, password } });
      setUser(user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="card login-card" onSubmit={submit}>
        <h1>
          <img src="/favicon.svg" alt="" width={36} height={36} /> PhysioFlow
        </h1>
        {setup && (
          <p className="muted">
            Erster Start: Legen Sie das Administratorkonto an. Das Passwort muss mindestens 10 Zeichen lang sein.
          </p>
        )}
        <TextField label="Benutzername" value={username} onChange={(v) => setUsername(v ?? "")} required autoFocus />
        {setup && <TextField label="Vollständiger Name" value={fullName} onChange={(v) => setFullName(v ?? "")} required />}
        <TextField label="Passwort" type="password" value={password} onChange={(v) => setPassword(v ?? "")} required />
        <ErrorBox error={error} />
        <button className="btn primary big" disabled={busy}>
          {setup ? "Konto anlegen" : "Anmelden"}
        </button>
      </form>
    </div>
  );
}
