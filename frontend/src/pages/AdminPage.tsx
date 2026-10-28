import { useState } from "react";
import { NavLink, useParams } from "react-router-dom";
import { api, type AuditEntry, type PatientListItem } from "../api";
import { ErrorBox } from "../components/fields";
import Modal from "../components/Modal";
import { TextField } from "../components/fields";
import { useApi } from "../hooks";
import { ACTION, ENTITY, FIELD, formatDate, formatDateTime } from "../labels";

export default function AdminPage() {
  const { tab = "betrieb" } = useParams();
  return (
    <div className="stack">
      <h1>Verwaltung</h1>
      <nav className="tabs">
        <NavLink to="/verwaltung" end>
          Betrieb &amp; Sicherheit
        </NavLink>
        <NavLink to="/verwaltung/datenschutz">Aufbewahrung &amp; Löschung</NavLink>
        <NavLink to="/verwaltung/protokoll">Änderungsprotokoll</NavLink>
      </nav>
      {tab === "betrieb" && <OpsTab />}
      {tab === "datenschutz" && <RetentionTab />}
      {tab === "protokoll" && <AuditTab />}
    </div>
  );
}

interface Ops {
  last_backup_at: string | null;
  last_backup_file: string | null;
  last_restore_test_at: string | null;
  idle_minutes: number;
  retention_years: number;
  cookie_secure: boolean;
}

interface Integrity {
  ok: boolean;
  problems: string[];
  schema: { current: string | null; head: string | null };
  files_hash_checked: number;
  counts: Record<string, number>;
}

export function ageDays(iso: string | null): number | null {
  return iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 86400000) : null;
}

function OpsTab() {
  const ops = useApi<Ops>("/admin/ops");
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const o = ops.data;
  const backupAge = ageDays(o?.last_backup_at ?? null);
  const testAge = ageDays(o?.last_restore_test_at ?? null);

  async function check() {
    setBusy(true);
    setError(null);
    try {
      setIntegrity(await api<Integrity>("/admin/integrity"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <ErrorBox error={ops.error ?? error} />
      {o && (
        <section className="card">
          <h2>Datensicherung</h2>
          <ul className="plain checks-list">
            <li className={backupAge === null || backupAge > 2 ? "warn" : "ok"}>
              Letztes Backup: {o.last_backup_at ? `${formatDateTime(o.last_backup_at)} (vor ${backupAge} Tag(en))` : "noch nie vermerkt"}
              {o.last_backup_file && <span className="muted block">{o.last_backup_file}</span>}
            </li>
            <li className={testAge === null || testAge > 100 ? "warn" : "ok"}>
              Letzter Wiederherstellungstest: {o.last_restore_test_at ? `${formatDateTime(o.last_restore_test_at)} (vor ${testAge} Tag(en))` : "noch nie durchgeführt"}
            </li>
            <li className={o.cookie_secure ? "ok" : "warn"}>Sichere Cookies (HTTPS): {o.cookie_secure ? "aktiv" : "AUS – nur für Entwicklung"}</li>
            <li className="ok">Automatische Abmeldung nach {o.idle_minutes} Minuten Inaktivität</li>
          </ul>
          <p className="muted">
            Backups mit <code>scripts/backup.sh</code> täglich erstellen und mit <code>scripts/restore-test.sh</code> mindestens vierteljährlich testen (siehe docs/BETRIEB.md).
          </p>
        </section>
      )}
      <section className="card stack">
        <h2>Integritätsprüfung</h2>
        <p className="muted">Prüft Datenbankschema, alle gespeicherten Dateien (Vorhandensein und Prüfsumme) und die lückenlose Rechnungsnummerierung.</p>
        <div className="actions">
          <button className="btn primary" onClick={check} disabled={busy}>
            {busy ? "Prüfe …" : "Jetzt prüfen"}
          </button>
        </div>
        {integrity && (
          <div>
            <p className={integrity.ok ? "ok-text" : "danger-text"}>{integrity.ok ? "✓ Alles in Ordnung" : "⚠ Probleme gefunden"}</p>
            <p className="muted">
              Schema {integrity.schema.current} · {integrity.files_hash_checked} Dateien geprüft ·{" "}
              {Object.entries(integrity.counts)
                .map(([k, v]) => `${v} ${k}`)
                .join(", ")}
            </p>
            {integrity.problems.length > 0 && (
              <ul className="plain compact">
                {integrity.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

interface RetentionRow {
  patient: PatientListItem;
  last_activity: string;
  retention_until: string;
  eligible: boolean;
}

function RetentionTab() {
  const [onlyEligible, setOnlyEligible] = useState(true);
  const { data, error, reload } = useApi<RetentionRow[]>(`/admin/retention?only_eligible=${onlyEligible}`);
  const [target, setTarget] = useState<RetentionRow | null>(null);
  const [done, setDone] = useState<string | null>(null);

  return (
    <div className="stack">
      <section className="card">
        <h2>Aufbewahrungsfristen</h2>
        <p className="muted">
          Patientenakten und Rechnungen werden nach Ablauf der Aufbewahrungsfrist (hier gerechnet ab der letzten Aktivität) zur Löschung vorgeschlagen. Gelöscht wird nur auf ausdrückliche Bestätigung. Die Frist ist
          in der Konfiguration einstellbar und sollte rechtlich geprüft werden.
        </p>
        <label className="check">
          <input type="checkbox" checked={onlyEligible} onChange={(e) => setOnlyEligible(e.target.checked)} />
          <span>Nur Akten mit abgelaufener Frist</span>
        </label>
      </section>
      <ErrorBox error={error} />
      {done && <p className="ok-text">{done}</p>}
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Patient</th>
              <th>Letzte Aktivität</th>
              <th>Aufbewahrung bis</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((r) => (
              <tr key={r.patient.id}>
                <td>
                  {r.patient.last_name}, {r.patient.first_name} <span className="muted">({r.patient.patient_number})</span>
                </td>
                <td>{formatDate(r.last_activity)}</td>
                <td className={r.eligible ? "danger-text" : undefined}>{formatDate(r.retention_until)}</td>
                <td className="row-actions">
                  <a className="btn small" href={`/api/patients/${r.patient.id}/export.zip`}>
                    Akte exportieren
                  </a>
                  <button className="btn small danger" onClick={() => setTarget(r)}>
                    Löschen …
                  </button>
                </td>
              </tr>
            ))}
            {data?.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  Keine Akten mit abgelaufener Aufbewahrungsfrist.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {target && (
        <EraseDialog
          row={target}
          onClose={() => setTarget(null)}
          onDone={(msg) => {
            setTarget(null);
            setDone(msg);
            reload();
          }}
        />
      )}
    </div>
  );
}

function EraseDialog({ row, onClose, onDone }: { row: RetentionRow; onClose: () => void; onDone: (msg: string) => void }) {
  const [number, setNumber] = useState("");
  const [reason, setReason] = useState(row.eligible ? "Aufbewahrungsfrist abgelaufen" : "");
  const [error, setError] = useState<string | null>(null);

  async function erase() {
    try {
      await api(`/admin/patients/${row.patient.id}/erase`, { method: "POST", body: { confirm_number: number, reason } });
      onDone(`Akte ${row.patient.patient_number} wurde gelöscht.`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Modal title="Akte unwiderruflich löschen" onClose={onClose}>
      <p className="ai-notice">
        Alle Daten von {row.patient.first_name} {row.patient.last_name} (Akte, Dateien, Termine, Rechnungen, Protokoll) werden endgültig gelöscht. Das kann nicht rückgängig gemacht werden.
        {!row.eligible && " Die Aufbewahrungsfrist ist noch nicht abgelaufen – bitte nur nach rechtlicher Prüfung löschen."}
      </p>
      <div className="form-grid">
        <TextField label={`Zur Bestätigung die Patientennummer eingeben (${row.patient.patient_number})`} value={number} onChange={(v) => setNumber(v ?? "")} wide autoFocus />
        <TextField label="Begründung" value={reason} onChange={(v) => setReason(v ?? "")} wide />
      </div>
      <ErrorBox error={error} />
      <div className="actions">
        <a className="btn" href={`/api/patients/${row.patient.id}/export.zip`}>
          Zuvor Akte exportieren
        </a>
        <button className="btn" onClick={onClose}>
          Abbrechen
        </button>
        <button className="btn danger" disabled={number.trim() !== row.patient.patient_number || !reason.trim()} onClick={erase}>
          Endgültig löschen
        </button>
      </div>
    </Modal>
  );
}

type AdminAudit = AuditEntry & { patient: PatientListItem | null };

function AuditTab() {
  const [action, setAction] = useState("");
  const [views, setViews] = useState(false);
  const q = new URLSearchParams({ include_views: String(views), limit: "200" });
  if (action) q.set("action", action);
  const { data, error } = useApi<AdminAudit[]>(`/admin/audit?${q}`);
  const [reasonOnly, setReasonOnly] = useState(false);

  return (
    <div className="stack">
      <div className="card form-grid">
        <div className="field">
          <span className="field-label">Aktion</span>
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">alle</option>
            {["create", "update", "correct", "void", "issue", "cancel", "export", "erase", "assist", "login", "login_failed", "logout_all"].map((a) => (
              <option key={a} value={a}>
                {ACTION[a] ?? a}
              </option>
            ))}
          </select>
        </div>
        <label className="check">
          <input type="checkbox" checked={views} onChange={(e) => setViews(e.target.checked)} />
          <span>Aktenzugriffe (Ansehen) einblenden</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={reasonOnly} onChange={(e) => setReasonOnly(e.target.checked)} />
          <span>Nur Einträge mit Begründung</span>
        </label>
      </div>
      <ErrorBox error={error} />
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Zeit</th>
              <th>Benutzer</th>
              <th>Vorgang</th>
              <th>Patient</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? [])
              .filter((e) => !reasonOnly || e.reason)
              .map((e) => (
                <tr key={e.id}>
                  <td>{formatDateTime(e.at)}</td>
                  <td>{e.user?.full_name ?? "–"}</td>
                  <td>
                    {ENTITY[e.entity_type] ?? e.entity_type} {ACTION[e.action] ?? e.action}
                  </td>
                  <td>{e.patient ? `${e.patient.last_name}, ${e.patient.first_name}` : "–"}</td>
                  <td className="small-text">
                    {e.reason && <em>Begründung: {e.reason}. </em>}
                    {e.action !== "create" &&
                      e.changes &&
                      Object.entries(e.changes)
                        .filter(([, v]) => typeof v === "object" && v !== null && "old" in v)
                        .slice(0, 4)
                        .map(([k, v]) => (
                          <span key={k} className="block">
                            {FIELD[k] ?? k}: <del>{String((v as { old: unknown }).old ?? "–")}</del> → <ins>{String((v as { new: unknown }).new ?? "–")}</ins>
                          </span>
                        ))}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

