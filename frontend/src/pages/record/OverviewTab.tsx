import { Link } from "react-router-dom";
import type { Anamnesis, Catalog, Diagnosis, Patient, Treatment } from "../../api";
import { INSURANCE, SEX, formatDate } from "../../labels";
import { Detail } from "./common";

export default function OverviewTab({
  patient: p,
  anamnesis,
  diagnoses,
  treatments,
  catalog,
  medical,
}: {
  patient: Patient;
  anamnesis: Anamnesis | undefined;
  diagnoses: Diagnosis[];
  treatments: Treatment[];
  catalog: Catalog;
  medical: boolean;
}) {
  const active = diagnoses.filter((d) => !d.voided && d.status === "active");
  const done = treatments.filter((t) => !t.voided);
  const address = [p.street, [p.postal_code, p.city].filter(Boolean).join(" ")].filter(Boolean).join(", ");

  return (
    <div className="grid-2">
      <section className="card">
        <h2>Stammdaten</h2>
        <dl className="details">
          <Detail label="Geschlecht" value={SEX[p.sex]} />
          <Detail label="Adresse" value={address} />
          <Detail label="Telefon" value={[p.phone, p.mobile].filter(Boolean).join(" / ")} />
          <Detail label="E-Mail" value={p.email} />
          <Detail label="Beruf" value={p.occupation} />
          <Detail label="Notfallkontakt" value={p.emergency_contact} />
          <Detail label="Versicherung" value={`${INSURANCE[p.insurance_type]}${p.insurance_name ? " – " + p.insurance_name : ""}`} />
          <Detail label="Versichertennr." value={p.insurance_number} />
          <Detail label="Verordner/in" value={p.referring_physician} />
          <Detail
            label="Einwilligungen"
            value={
              [p.consent_treatment && "Behandlung", p.consent_data_processing && "Datenverarbeitung"].filter(Boolean).join(", ") +
              (p.consent_date ? ` (${formatDate(p.consent_date)})` : "")
            }
          />
          <Detail label="Notizen" value={p.notes} />
        </dl>
      </section>

      {medical && (
      <section className="card">
        <h2>Aktuelle Situation</h2>
        {anamnesis ? (
          <dl className="details">
            <Detail label="Hauptbeschwerde" value={anamnesis.chief_complaint} />
            <Detail label="Schmerz bei Aufnahme" value={anamnesis.pain_current !== null ? `${anamnesis.pain_current}/10` : null} />
            <Detail label="Therapieziele" value={anamnesis.goals} />
            <Detail
              label="Warnzeichen"
              value={anamnesis.red_flags.length > 0 && <span className="danger-text">⚠ {anamnesis.red_flags.map((f) => catalog.red_flags[f]).join(", ")}</span>}
            />
          </dl>
        ) : (
          <p className="muted">
            Noch keine Anamnese. <Link to={`/patienten/${p.id}/anamnese`}>Jetzt erfassen →</Link>
          </p>
        )}
        <h3>Aktive Diagnosen</h3>
        {active.length === 0 ? (
          <p className="muted">
            Keine. <Link to={`/patienten/${p.id}/diagnosen`}>Diagnose erfassen →</Link>
          </p>
        ) : (
          <ul className="plain">
            {active.map((d) => (
              <li key={d.id}>
                {d.icd10_code && <code className="icd">{d.icd10_code}</code>} {d.description}
                {d.is_primary && <span className="badge accent">Haupt</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
      )}

      {medical && (
      <section className="card wide">
        <div className="page-head">
          <h2>Letzte Behandlungen ({done.length})</h2>
          <Link to={`/patienten/${p.id}/behandlungen`} className="btn">
            Alle Behandlungen
          </Link>
        </div>
        {done.length === 0 ? (
          <p className="muted">Noch keine Behandlung dokumentiert.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Maßnahmen</th>
                  <th>NRS vorher → nachher</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {done.slice(0, 8).map((t) => (
                  <tr key={t.id}>
                    <td>{formatDate(t.treated_on)}</td>
                    <td>{t.measures.join(", ") || "–"}</td>
                    <td>
                      {t.pain_before ?? "–"} → {t.pain_after ?? "–"}
                    </td>
                    <td>{t.status === "draft" ? <span className="badge warn">Entwurf</span> : "abgeschlossen"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      )}
    </div>
  );
}
