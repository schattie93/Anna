import { useEffect, useState } from "react";
import { api, type PatientListItem } from "../api";
import { formatDate } from "../labels";

/** Auswahlfeld für Patienten mit Suche (Name, Nummer, Ort). */
export default function PatientPicker({ value, onChange, autoFocus }: { value: PatientListItem | null; onChange: (p: PatientListItem | null) => void; autoFocus?: boolean }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PatientListItem[]>([]);

  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    const handle = setTimeout(() => api<PatientListItem[]>(`/patients?${new URLSearchParams({ q, limit: "8" })}`).then(setResults, () => setResults([])), 150);
    return () => clearTimeout(handle);
  }, [q]);

  if (value) {
    return (
      <div className="picked">
        <strong>
          {value.last_name}, {value.first_name}
        </strong>
        <span className="muted"> · geb. {formatDate(value.birth_date)}</span>
        <button type="button" className="btn small" onClick={() => onChange(null)}>
          ändern
        </button>
      </div>
    );
  }
  return (
    <div className="picker">
      <input type="search" value={q} autoFocus={autoFocus} placeholder="Patient suchen …" onChange={(e) => setQ(e.target.value)} />
      {results.length > 0 && (
        <ul className="picker-list">
          {results.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => {
                  onChange(p);
                  setQ("");
                }}
              >
                <strong>
                  {p.last_name}, {p.first_name}
                </strong>
                <span className="muted">
                  {" "}
                  · geb. {formatDate(p.birth_date)} · {p.patient_number}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
