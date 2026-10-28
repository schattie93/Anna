import { useState, type FormEvent } from "react";
import { api, type Indication, type PracticeSettings, type Role, type User } from "../api";
import { useAuth, useUser } from "../auth";
import { ErrorBox, Select, TextField } from "../components/fields";
import { useApi } from "../hooks";
import { ROLE } from "../labels";

export default function SettingsPage() {
  const user = useUser();
  return (
    <div className="stack">
      <h1>Einstellungen</h1>
      <PasswordForm />
      <SessionsCard />
      {user.role === "admin" && <PracticeForm />}
      {user.role === "admin" && <IndicationCatalog />}
      {user.role === "admin" && <UserAdmin currentUserId={user.id} />}
    </div>
  );
}

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    try {
      await api("/auth/password", { method: "POST", body: { current_password: current, new_password: next } });
      setCurrent("");
      setNext("");
      setMsg("Passwort geändert.");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="wide">Eigenes Passwort ändern</h2>
      <TextField label="Aktuelles Passwort" type="password" value={current} onChange={(v) => setCurrent(v ?? "")} required />
      <TextField label="Neues Passwort" type="password" value={next} onChange={(v) => setNext(v ?? "")} required hint="mindestens 10 Zeichen" />
      <div className="wide">
        <ErrorBox error={error} />
        {msg && <p className="ok-text">{msg}</p>}
        <button className="btn primary">Passwort ändern</button>
      </div>
    </form>
  );
}

function UserAdmin({ currentUserId }: { currentUserId: number }) {
  const { data: users, reload } = useApi<User[]>("/users");
  const [form, setForm] = useState({ username: "", full_name: "", password: "", role: "therapist" as Role });
  const [error, setError] = useState<string | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/users", { method: "POST", body: form });
      setForm({ username: "", full_name: "", password: "", role: "therapist" });
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function update(id: number, body: Partial<User> & { password?: string }) {
    setError(null);
    try {
      await api(`/users/${id}`, { method: "PATCH", body });
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function resetPassword(u: User) {
    const password = window.prompt(`Neues Passwort für ${u.full_name} (mind. 10 Zeichen):`);
    if (password) update(u.id, { password });
  }

  return (
    <section className="card stack">
      <h2>Benutzerverwaltung</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Benutzername</th>
              <th>Rolle</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id}>
                <td>{u.full_name}</td>
                <td>{u.username}</td>
                <td>{ROLE[u.role]}</td>
                <td>{u.is_active ? "aktiv" : <span className="badge">deaktiviert</span>}</td>
                <td className="row-actions">
                  <button className="btn small" onClick={() => resetPassword(u)}>
                    Passwort setzen
                  </button>
                  {u.id !== currentUserId && (
                    <button className="btn small" onClick={() => update(u.id, { is_active: !u.is_active })}>
                      {u.is_active ? "Deaktivieren" : "Aktivieren"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="form-grid" onSubmit={create}>
        <h3 className="wide">Neuen Benutzer anlegen</h3>
        <TextField label="Vollständiger Name" value={form.full_name} onChange={(v) => setForm({ ...form, full_name: v ?? "" })} required />
        <TextField label="Benutzername" value={form.username} onChange={(v) => setForm({ ...form, username: v ?? "" })} required />
        <TextField
          label="Startpasswort"
          type="password"
          value={form.password}
          onChange={(v) => setForm({ ...form, password: v ?? "" })}
          required
          hint="mindestens 10 Zeichen"
        />
        <Select label="Rolle" value={form.role} options={ROLE as Record<Role, string>} onChange={(v) => setForm({ ...form, role: v })} />
        <div className="wide">
          <ErrorBox error={error} />
          <button className="btn primary">Benutzer anlegen</button>
        </div>
      </form>
    </section>
  );
}

const PRACTICE_LABELS: [keyof PracticeSettings, string, boolean?][] = [
  ["practice_name", "Praxisname"],
  ["practice_owner", "Inhaber/in"],
  ["practice_address", "Adresse (eine Zeile)"],
  ["practice_phone", "Telefon"],
  ["practice_email", "E-Mail"],
  ["practice_tax_number", "Steuernummer"],
  ["practice_ik", "Institutionskennzeichen (IK)"],
  ["practice_bank", "Bank"],
  ["practice_iban", "IBAN"],
  ["practice_bic", "BIC"],
  ["invoice_payment_days", "Zahlungsziel (Tage)"],
  ["invoice_vat_note", "Umsatzsteuer-Hinweis auf Rechnungen", true],
  ["invoice_footer", "Fußzeile auf Rechnungen", true],
];

function PracticeForm() {
  const { data, reload } = useApi<PracticeSettings>("/settings/practice");
  const [values, setValues] = useState<PracticeSettings | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = values ?? data;
  if (!form) return null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    try {
      await api("/settings/practice", { method: "PUT", body: form });
      setMsg("Praxisdaten gespeichert.");
      setValues(null);
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="wide">Praxisdaten (Briefkopf von Berichten, Rechnungen und Übungsplänen)</h2>
      {PRACTICE_LABELS.map(([key, label, wide]) => (
        <TextField key={key} label={label} wide={wide} value={form[key]} onChange={(v) => setValues({ ...form, [key]: v })} />
      ))}
      <div className="wide">
        <ErrorBox error={error} />
        {msg && <p className="ok-text">{msg}</p>}
        <button className="btn primary">Speichern</button>
      </div>
    </form>
  );
}

function SessionsCard() {
  const { setUser } = useAuth();
  const [busy, setBusy] = useState(false);
  return (
    <section className="card stack">
      <h2>Sitzungen</h2>
      <p className="muted">Meldet Sie auf allen Geräten ab, z. B. wenn ein Tablet verloren ging oder unbeaufsichtigt angemeldet blieb.</p>
      <div className="actions">
        <button
          className="btn danger"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await api("/auth/logout-all", { method: "POST" });
            setUser(null);
          }}
        >
          Auf allen Geräten abmelden
        </button>
      </div>
    </section>
  );
}

function IndicationCatalog() {
  const { data, reload } = useApi<Indication[]>("/indications?include_inactive=true");
  const [form, setForm] = useState({ key: "", name: "", max: "", orienting: "" });
  const [error, setError] = useState<string | null>(null);
  const toNum = (v: string) => (v.trim() ? Math.max(1, Number(v) || 1) : null);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/indications", { method: "POST", body: { key: form.key, name: form.name, max_units_per_rx: toNum(form.max), orienting_total_units: toNum(form.orienting) } });
      setForm({ key: "", name: "", max: "", orienting: "" });
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card stack">
      <h2>Heilmittelkatalog der Praxis</h2>
      <p className="muted">
        Tragen Sie hier die Indikationsschlüssel mit Höchstmenge je Verordnung und orientierender Behandlungsmenge aus dem <strong>aktuellen</strong> Heilmittelkatalog ein. Die Software prüft damit die
        Verordnungsmengen. Es sind bewusst keine Werte vorbelegt, damit nichts Veraltetes aus der Software übernommen wird.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Schlüssel</th>
              <th>Bezeichnung</th>
              <th>Höchstmenge je Verordnung</th>
              <th>Orientierende Menge</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((i) => (
              <tr key={i.id} className={i.active ? undefined : "struck"}>
                <td>{i.key}</td>
                <td>{i.name}</td>
                <td>{i.max_units_per_rx ?? "–"}</td>
                <td>{i.orienting_total_units ?? "–"}</td>
                <td className="row-actions">
                  <button
                    className="btn small"
                    onClick={async () => {
                      await api(`/indications/${i.id}`, { method: "PUT", body: { key: i.key, name: i.name, max_units_per_rx: i.max_units_per_rx, orienting_total_units: i.orienting_total_units, note: i.note, active: !i.active } });
                      reload();
                    }}
                  >
                    {i.active ? "Deaktivieren" : "Aktivieren"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="form-grid" onSubmit={add}>
        <TextField label="Indikationsschlüssel" value={form.key} onChange={(v) => setForm({ ...form, key: v ?? "" })} required placeholder="z. B. WS1" />
        <TextField label="Bezeichnung" value={form.name} onChange={(v) => setForm({ ...form, name: v ?? "" })} required />
        <TextField label="Höchstmenge je Verordnung" type="number" value={form.max} onChange={(v) => setForm({ ...form, max: v ?? "" })} />
        <TextField label="Orientierende Behandlungsmenge" type="number" value={form.orienting} onChange={(v) => setForm({ ...form, orienting: v ?? "" })} />
        <div className="wide">
          <ErrorBox error={error} />
          <button className="btn primary">Eintrag hinzufügen</button>
        </div>
      </form>
    </section>
  );
}
