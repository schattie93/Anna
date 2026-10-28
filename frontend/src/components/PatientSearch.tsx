import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type PatientListItem } from "../api";
import { INSURANCE, formatDate } from "../labels";

export default function PatientSearch({ autoFocus, showAll }: { autoFocus?: boolean; showAll?: boolean }) {
  const [q, setQ] = useState("");
  const [archived, setArchived] = useState(false);
  const [results, setResults] = useState<PatientListItem[] | null>(null);

  useEffect(() => {
    if (!q.trim() && !showAll) {
      setResults(null);
      return;
    }
    const handle = setTimeout(() => {
      const params = new URLSearchParams({ q, include_archived: String(archived) });
      api<PatientListItem[]>(`/patients?${params}`).then(setResults, () => setResults([]));
    }, 200);
    return () => clearTimeout(handle);
  }, [q, archived, showAll]);

  return (
    <div className="search">
      <input
        type="search"
        className="search-input"
        placeholder="Patient suchen: Name, Patientennummer oder Ort …"
        value={q}
        autoFocus={autoFocus}
        onChange={(e) => setQ(e.target.value)}
      />
      {showAll && (
        <label className="check">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          <span>Archivierte anzeigen</span>
        </label>
      )}
      {results && (
        <ul className="list card">
          {results.length === 0 && <li className="muted">Keine Treffer.</li>}
          {results.map((p) => (
            <li key={p.id}>
              <Link to={`/patienten/${p.id}`}>
                <strong>
                  {p.last_name}, {p.first_name}
                  {p.archived && <span className="badge">archiviert</span>}
                </strong>
                <span className="muted">
                  {p.patient_number} · geb. {formatDate(p.birth_date)}
                  {p.city ? ` · ${p.city}` : ""} · {INSURANCE[p.insurance_type]}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
