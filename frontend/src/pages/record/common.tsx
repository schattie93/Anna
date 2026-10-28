import { useState, type ReactNode } from "react";
import { api, type Catalog, type MedicalMeta } from "../../api";
import { ReasonDialog } from "../../components/fields";
import { formatDateTime } from "../../labels";

export interface TabProps<T> {
  patientId: number;
  catalog: Catalog;
  entries: T[];
  reload: () => void;
}

export function EntryCard({
  entry,
  title,
  badges,
  voidPath,
  onEdit,
  reload,
  children,
}: {
  entry: MedicalMeta;
  title: ReactNode;
  badges?: ReactNode;
  voidPath: string;
  onEdit: () => void;
  reload: () => void;
  children: ReactNode;
}) {
  const [voiding, setVoiding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function doVoid(reason: string) {
    try {
      await api(voidPath, { method: "POST", body: { reason } });
      setVoiding(false);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <article className={entry.voided ? "card entry voided" : "card entry"}>
      <header className="entry-head">
        <h3>
          {title}
          {badges}
          {entry.voided && <span className="badge">storniert</span>}
        </h3>
        {!entry.voided && (
          <div className="entry-actions">
            <button className="btn small" onClick={onEdit}>
              Bearbeiten
            </button>
            <button className="btn small danger" onClick={() => setVoiding(true)}>
              Stornieren
            </button>
          </div>
        )}
      </header>
      {children}
      <footer className="entry-meta muted">
        {entry.created_by.full_name} · erstellt {formatDateTime(entry.created_at)}
        {entry.updated_at !== entry.created_at && ` · zuletzt geändert ${formatDateTime(entry.updated_at)}`}
        {entry.voided && ` · storniert: ${entry.void_reason}`}
      </footer>
      {error && <div className="error">{error}</div>}
      {voiding && (
        <ReasonDialog title="Eintrag stornieren" confirmLabel="Stornieren" onConfirm={doVoid} onCancel={() => setVoiding(false)} />
      )}
    </article>
  );
}

/** Zeigt ein Feld nur an, wenn es befüllt ist. */
export function Detail({ label, value }: { label: string; value: ReactNode }) {
  if (value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) return null;
  return (
    <div className="detail">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function TabHead({ title, onNew, newLabel }: { title: string; onNew?: () => void; newLabel: string }) {
  return (
    <div className="page-head">
      <h2>{title}</h2>
      {onNew && (
        <button className="btn primary" onClick={onNew}>
          + {newLabel}
        </button>
      )}
    </div>
  );
}

export function useVoidedToggle() {
  const [showVoided, setShowVoided] = useState(false);
  const toggle = (
    <label className="check">
      <input type="checkbox" checked={showVoided} onChange={(e) => setShowVoided(e.target.checked)} />
      <span>Stornierte Einträge anzeigen</span>
    </label>
  );
  return { showVoided, toggle };
}
