import { useState } from "react";
import { Link } from "react-router-dom";
import type { BillingSummary, Stats } from "../api";
import BarChart from "../components/BarChart";
import { ErrorBox } from "../components/fields";
import { useApi } from "../hooks";
import { MONTHS, euro, formatDate } from "../labels";

export default function StatsPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const stats = useApi<Stats>(`/stats?year=${year}`);
  const billing = useApi<BillingSummary>(`/billing/summary?year=${year}`);
  const s = stats.data;
  const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v * 100)} %`);

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Auswertung</h1>
        <div className="actions">
          <button className="btn" onClick={() => setYear(year - 1)}>
            ‹
          </button>
          <strong className="year">{year}</strong>
          <button className="btn" onClick={() => setYear(year + 1)}>
            ›
          </button>
        </div>
      </div>
      <ErrorBox error={stats.error} />
      {s && (
        <>
          <div className="stats">
            <div className="stat">
              <span className="stat-value">{s.treatments_year}</span>
              <span className="stat-label">Behandlungen</span>
            </div>
            <div className="stat">
              <span className="stat-value">{Math.round(s.treatment_minutes_year / 60)} h</span>
              <span className="stat-label">Behandlungszeit</span>
            </div>
            <div className="stat">
              <span className="stat-value">{pct(s.appointments.no_show_rate)}</span>
              <span className="stat-label">nicht erschienen</span>
            </div>
            <div className="stat">
              <span className="stat-value">{pct(s.appointments.cancel_rate)}</span>
              <span className="stat-label">abgesagt</span>
            </div>
          </div>

          <div className="grid-2">
            <section className="card">
              <h2>Behandlungen pro Monat</h2>
              <BarChart title="Behandlungen pro Monat" bars={s.treatments_by_month.map((v, i) => ({ label: MONTHS[i], value: v }))} />
            </section>
            <section className="card">
              <h2>Patienten pro Monat</h2>
              <BarChart title="Behandelte Patienten pro Monat" bars={s.patients_by_month.map((v, i) => ({ label: MONTHS[i], value: v }))} />
            </section>
            {billing.data && (
              <section className="card">
                <h2>Umsatz pro Monat ({euro(billing.data.revenue_year_cents)})</h2>
                <BarChart title="Umsatz pro Monat" bars={billing.data.revenue_by_month_cents.map((v, i) => ({ label: MONTHS[i], value: v / 100 }))} format={(v) => `${Math.round(v)} €`} />
              </section>
            )}
            <section className="card">
              <h2>Häufigste Maßnahmen</h2>
              {s.measures.length === 0 ? (
                <p className="muted">Keine Daten.</p>
              ) : (
                <ul className="plain meter">
                  {s.measures.map(([name, n]) => (
                    <li key={name}>
                      <span>{name}</span>
                      <div className="bar">
                        <i style={{ width: `${(n / s.measures[0][1]) * 100}%` }} />
                      </div>
                      <strong>{n}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section className="card">
            <h2>Dokumentationsvollständigkeit</h2>
            <ul className="plain checks-list">
              <li className={s.documentation.draft_treatments_overdue.length ? "warn" : "ok"}>
                {s.documentation.draft_treatments_overdue.length} Behandlungsentwürfe älter als 1 Tag noch nicht abgeschlossen
                {s.documentation.draft_treatments_overdue.slice(0, 6).map((t) => (
                  <Link key={t.id} to={`/patienten/${t.patient_id}/behandlungen`} className="chip-link">
                    {formatDate(t.treated_on)}
                  </Link>
                ))}
              </li>
              <li className={s.documentation.gkv_treatments_without_prescription ? "warn" : "ok"}>{s.documentation.gkv_treatments_without_prescription} GKV-Behandlungen ohne zugeordnete Verordnung</li>
              <li className={s.documentation.patients_without_data_consent.length ? "warn" : "ok"}>
                {s.documentation.patients_without_data_consent.length} von {s.documentation.active_patients} aktiven Patienten ohne Einwilligung zur Datenverarbeitung
                {s.documentation.patients_without_data_consent.slice(0, 6).map((id) => (
                  <Link key={id} to={`/patienten/${id}/bearbeiten`} className="chip-link">
                    #{id}
                  </Link>
                ))}
              </li>
              <li className={s.documentation.treated_patients_without_anamnesis.length ? "warn" : "ok"}>
                {s.documentation.treated_patients_without_anamnesis.length} behandelte Patienten ohne Anamnese
                {s.documentation.treated_patients_without_anamnesis.slice(0, 6).map((id) => (
                  <Link key={id} to={`/patienten/${id}/anamnese`} className="chip-link">
                    #{id}
                  </Link>
                ))}
              </li>
              <li className={s.documentation.treated_patients_without_diagnosis.length ? "warn" : "ok"}>
                {s.documentation.treated_patients_without_diagnosis.length} behandelte Patienten ohne Diagnose
                {s.documentation.treated_patients_without_diagnosis.slice(0, 6).map((id) => (
                  <Link key={id} to={`/patienten/${id}/diagnosen`} className="chip-link">
                    #{id}
                  </Link>
                ))}
              </li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
