import { Link } from "react-router-dom";
import { api, type Dashboard } from "../api";
import { useUser } from "../auth";
import { ageDays } from "./AdminPage";
import { ErrorBox } from "../components/fields";
import PatientSearch from "../components/PatientSearch";
import { useApi } from "../hooks";
import { APPT_STATUS, formatDate, formatTime } from "../labels";

export default function DashboardPage() {
  const { data, error, reload } = useApi<Dashboard>("/dashboard");
  const user = useUser();
  const medical = user.role !== "reception";
  const ops = useApi<{ last_backup_at: string | null; last_restore_test_at: string | null }>(user.role === "admin" ? "/admin/ops" : null);
  const backupAge = ageDays(ops.data?.last_backup_at ?? null);
  const testAge = ageDays(ops.data?.last_restore_test_at ?? null);

  return (
    <div className="stack">
      {ops.data && (backupAge === null || backupAge > 2 || testAge === null || testAge > 100) && (
        <Link to="/verwaltung" className="ai-notice block">
          ⚠ Datensicherung:{" "}
          {backupAge === null ? "Es wurde noch kein Backup vermerkt." : backupAge > 2 ? `Das letzte Backup ist ${backupAge} Tage alt.` : ""}{" "}
          {testAge === null || testAge > 100 ? "Ein Wiederherstellungstest steht aus." : ""}
        </Link>
      )}
      <PatientSearch autoFocus />
      <ErrorBox error={error} />
      {data && (
        <>
          <div className="stats">
            <div className="stat">
              <span className="stat-value">{data.patient_count}</span>
              <span className="stat-label">aktive Patienten</span>
            </div>
            <div className="stat">
              <span className="stat-value">{data.treatments_today}</span>
              <span className="stat-label">Behandlungen heute</span>
            </div>
            <div className="stat">
              <span className="stat-value">{data.open_treatments.length}</span>
              <span className="stat-label">offene Dokumentationen</span>
            </div>
            <Link to="/patienten/neu" className="stat stat-action">
              <span className="stat-value">+</span>
              <span className="stat-label">Neuer Patient</span>
            </Link>
          </div>

          <div className="grid-2">
            <section className="card">
              <div className="page-head">
                <h2>Heute</h2>
                <Link to="/termine" className="btn small">
                  Kalender
                </Link>
              </div>
              {data.appointments_today.length === 0 ? (
                <p className="muted">Keine Termine heute.</p>
              ) : (
                <ul className="list">
                  {data.appointments_today.map((a) => (
                    <li key={a.id}>
                      <Link to={a.patient ? `/patienten/${a.patient.id}` : "/termine"}>
                        <strong>
                          {formatTime(a.start)} {a.patient ? `${a.patient.last_name}, ${a.patient.first_name}` : (a.title ?? "Blockzeit")}
                        </strong>
                        <span className="muted">
                          {a.therapist.full_name}
                          {a.prescription_label ? ` · ${a.prescription_label}` : ""} · {APPT_STATUS[a.status]}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            {(data.follow_ups_due.length > 0 || data.rx_attention.length > 0) && (
              <section className="card">
                <h2>Zu erledigen</h2>
                <ul className="list">
                  {data.follow_ups_due.map((f) => (
                    <li key={`f${f.id}`} className="follow">
                      <Link to={`/patienten/${f.patient.id}`}>
                        <strong>
                          {f.patient.last_name}, {f.patient.first_name}
                        </strong>
                        <span className="muted">
                          Wiedervorlage {formatDate(f.due_on)}: {f.text}
                        </span>
                      </Link>
                      <button
                        className="btn small"
                        onClick={async () => {
                          await api(`/follow-ups/${f.id}`, { method: "PATCH", body: { done: true } });
                          reload();
                        }}
                      >
                        ✓
                      </button>
                    </li>
                  ))}
                  {medical &&
                    data.rx_attention.map((r) => (
                      <li key={`r${r.prescription_id}`}>
                        <Link to={`/patienten/${r.patient.id}/verordnungen`}>
                          <strong>
                            {r.patient.last_name}, {r.patient.first_name} · {r.measure} {r.units_done}/{r.total_units}
                          </strong>
                          {r.warnings.map((w) => (
                            <span key={w.text} className={w.level === "warn" ? "danger-text small-text" : "muted"}>
                              {w.level === "warn" ? "⚠ " : "ℹ "}
                              {w.text}
                            </span>
                          ))}
                        </Link>
                      </li>
                    ))}
                </ul>
              </section>
            )}
          </div>

          <div className="grid-2">
            <section className="card">
              <h2>Offene Dokumentationen</h2>
              {data.open_treatments.length === 0 ? (
                <p className="muted">Alles dokumentiert.</p>
              ) : (
                <ul className="list">
                  {data.open_treatments.map((t) => (
                    <li key={t.id}>
                      <Link to={`/patienten/${t.patient_id}/behandlungen`}>
                        <strong>
                          {t.patient.last_name}, {t.patient.first_name}
                        </strong>
                        <span className="muted">Behandlung vom {formatDate(t.treated_on)} – Entwurf</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="card">
              <h2>Zuletzt bearbeitet</h2>
              {data.recent_patients.length === 0 ? (
                <p className="muted">Noch keine Patienten geöffnet.</p>
              ) : (
                <ul className="list">
                  {data.recent_patients.map((p) => (
                    <li key={p.id}>
                      <Link to={`/patienten/${p.id}`}>
                        <strong>
                          {p.last_name}, {p.first_name}
                        </strong>
                        <span className="muted">
                          {p.patient_number} · geb. {formatDate(p.birth_date)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
