import { Link } from "react-router-dom";
import type { Dashboard } from "../api";
import { ErrorBox } from "../components/fields";
import PatientSearch from "../components/PatientSearch";
import { useApi } from "../hooks";
import { formatDate } from "../labels";

export default function DashboardPage() {
  const { data, error } = useApi<Dashboard>("/dashboard");

  return (
    <div className="stack">
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
