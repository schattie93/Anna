import type { AuditEntry } from "../../api";
import { ErrorBox } from "../../components/fields";
import { useApi } from "../../hooks";
import { ACTION, ENTITY, FIELD, formatDateTime } from "../../labels";

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "–";
  if (Array.isArray(value)) return value.join(", ") || "–";
  if (typeof value === "boolean") return value ? "ja" : "nein";
  return String(value);
}

function isDiff(v: unknown): v is { old: unknown; new: unknown } {
  return typeof v === "object" && v !== null && "old" in v && "new" in v;
}

export default function HistoryTab({ patientId }: { patientId: number }) {
  const { data, error } = useApi<AuditEntry[]>(`/patients/${patientId}/history`);
  if (error) return <ErrorBox error={error} />;
  if (!data) return <p className="muted">Lade …</p>;

  return (
    <div className="stack">
      <h2>Änderungsprotokoll</h2>
      <p className="muted">Alle Anlagen, Änderungen, Korrekturen und Stornierungen dieser Akte – nicht veränderbar.</p>
      <div className="card">
        <ul className="timeline">
          {data.map((e) => (
            <li key={e.id}>
              <div>
                <strong>
                  {ENTITY[e.entity_type] ?? e.entity_type} {ACTION[e.action] ?? e.action}
                </strong>{" "}
                <span className="muted">
                  {formatDateTime(e.at)} · {e.user?.full_name ?? "System"}
                </span>
              </div>
              {e.reason && <div className="reason">Begründung: {e.reason}</div>}
              {e.action !== "create" && e.changes && (
                <ul className="changes">
                  {Object.entries(e.changes).map(([field, change]) =>
                    isDiff(change) ? (
                      <li key={field}>
                        <strong>{FIELD[field] ?? field}</strong>: <del>{show(change.old)}</del> → <ins>{show(change.new)}</ins>
                      </li>
                    ) : null,
                  )}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
