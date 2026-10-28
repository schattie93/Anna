import { useEffect, useState, type FormEvent } from "react";
import { api, type Exercise, type ExercisePlan, type PlanItemData } from "../../api";
import { ErrorBox, TextArea, TextField } from "../../components/fields";
import { formatDate, today } from "../../labels";
import { EntryCard, TabHead, useVoidedToggle } from "./common";

function dose(i: { sets: number | null; reps: number | null; hold_seconds: number | null; frequency: string | null }): string {
  return [i.sets && i.reps ? `${i.sets} × ${i.reps}` : i.reps ? `${i.reps} Wdh.` : i.sets ? `${i.sets} Durchgänge` : null, i.hold_seconds ? `${i.hold_seconds} s halten` : null, i.frequency].filter(Boolean).join(" · ");
}

export default function ExercisesTab({ patientId, entries, reload }: { patientId: number; entries: ExercisePlan[]; reload: () => void }) {
  const [editing, setEditing] = useState<ExercisePlan | "new" | null>(null);
  const { showVoided, toggle } = useVoidedToggle();

  if (editing) {
    return (
      <PlanForm
        patientId={patientId}
        entry={editing === "new" ? null : editing}
        onDone={() => {
          setEditing(null);
          reload();
        }}
        onCancel={() => setEditing(null)}
      />
    );
  }

  const visible = entries.filter((p) => showVoided || !p.voided);
  return (
    <div className="stack">
      <TabHead title="Übungspläne (Hausübungen)" newLabel="Neuer Übungsplan" onNew={() => setEditing("new")} />
      {visible.length === 0 && <p className="muted card">Noch kein Übungsplan. Pläne lassen sich als PDF ausdrucken und mitgeben.</p>}
      {visible.map((p) => (
        <EntryCard
          key={p.id}
          entry={p}
          title={`${p.title} · ${formatDate(p.issued_on)}`}
          voidPath={`/patients/${patientId}/exercise-plans/${p.id}/void`}
          onEdit={() => setEditing(p)}
          reload={reload}
        >
          <ol className="plan-list">
            {p.items.map((i) => (
              <li key={i.id}>
                <strong>{i.title}</strong>
                {dose(i) && <span className="muted"> – {dose(i)}</span>}
              </li>
            ))}
          </ol>
          {!p.voided &&
            (p.items.some((i) => !i.approved) ? (
              <p className="ai-notice">Enthält noch nicht freigegebene Übungen ({p.items.filter((i) => !i.approved).map((i) => i.title).join(", ")}). Bitte in der Übungsbibliothek prüfen und freigeben, dann lässt sich der Plan drucken.</p>
            ) : (
              <p>
                <a className="btn" href={`/api/patients/${patientId}/exercise-plans/${p.id}/pdf`} target="_blank" rel="noreferrer">
                  🖨 PDF / Drucken
                </a>
              </p>
            ))}
        </EntryCard>
      ))}
      {entries.some((p) => p.voided) && toggle}
    </div>
  );
}

function PlanForm({ patientId, entry, onDone, onCancel }: { patientId: number; entry: ExercisePlan | null; onDone: () => void; onCancel: () => void }) {
  const [title, setTitle] = useState(entry?.title ?? "Hausübungen");
  const [issued, setIssued] = useState(entry?.issued_on ?? today());
  const [notes, setNotes] = useState<string | null>(entry?.notes ?? null);
  const [items, setItems] = useState<PlanItemData[]>(
    entry?.items.map(({ exercise_id, title, instructions, sets, reps, hold_seconds, frequency, notes }) => ({ exercise_id, title, instructions, sets, reps, hold_seconds, frequency, notes })) ?? [],
  );
  const [q, setQ] = useState("");
  const [library, setLibrary] = useState<Exercise[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handle = setTimeout(() => api<Exercise[]>(`/exercises?${new URLSearchParams({ q })}`).then(setLibrary, () => setLibrary([])), 150);
    return () => clearTimeout(handle);
  }, [q]);

  const add = (e: Exercise) =>
    setItems((list) => [
      ...list,
      { exercise_id: e.id, title: e.title, instructions: e.instructions, sets: e.default_sets, reps: e.default_reps, hold_seconds: e.default_hold_seconds, frequency: "täglich", notes: null },
    ]);
  const update = (i: number, patch: Partial<PlanItemData>) => setItems((list) => list.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  const move = (i: number, dir: number) =>
    setItems((list) => {
      const j = i + dir;
      if (j < 0 || j >= list.length) return list;
      const copy = [...list];
      [copy[i], copy[j]] = [copy[j], copy[i]];
      return copy;
    });
  const num = (v: string) => (v === "" ? null : Math.max(1, Number(v) || 1));

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const body = { title, issued_on: issued, notes, items };
      if (entry) await api(`/patients/${patientId}/exercise-plans/${entry.id}`, { method: "PUT", body });
      else await api(`/patients/${patientId}/exercise-plans`, { method: "POST", body });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <h2>{entry ? "Übungsplan bearbeiten" : "Neuer Übungsplan"}</h2>
      <section className="card form-grid">
        <TextField label="Titel" value={title} onChange={(v) => setTitle(v ?? "")} required />
        <TextField label="Datum" type="date" value={issued} onChange={(v) => setIssued(v ?? "")} required />
        <TextArea label="Hinweise für den Patienten" value={notes} onChange={setNotes} rows={2} />
      </section>

      <section className="card">
        <h3>Übungen im Plan ({items.length})</h3>
        {items.length === 0 && <p className="muted">Unten Übungen aus der Bibliothek antippen, um sie hinzuzufügen.</p>}
        {items.map((it, i) => (
          <div key={i} className="plan-item">
            <div className="plan-item-head">
              <strong>
                {i + 1}. {it.title}
              </strong>
              <span className="actions">
                <button type="button" className="btn small" onClick={() => move(i, -1)} disabled={i === 0} aria-label="nach oben">
                  ↑
                </button>
                <button type="button" className="btn small" onClick={() => move(i, 1)} disabled={i === items.length - 1} aria-label="nach unten">
                  ↓
                </button>
                <button type="button" className="btn small danger" onClick={() => setItems((l) => l.filter((_, idx) => idx !== i))}>
                  Entfernen
                </button>
              </span>
            </div>
            <div className="form-grid">
              <TextField label="Sätze" type="number" value={it.sets?.toString() ?? null} onChange={(v) => update(i, { sets: num(v ?? "") })} />
              <TextField label="Wiederholungen" type="number" value={it.reps?.toString() ?? null} onChange={(v) => update(i, { reps: num(v ?? "") })} />
              <TextField label="Halten (Sek.)" type="number" value={it.hold_seconds?.toString() ?? null} onChange={(v) => update(i, { hold_seconds: num(v ?? "") })} />
              <TextField label="Häufigkeit" value={it.frequency} onChange={(v) => update(i, { frequency: v })} />
              <TextArea label="Anleitung" value={it.instructions} onChange={(v) => update(i, { instructions: v })} rows={2} />
              <TextField label="Hinweis (nur für diesen Patienten)" value={it.notes} onChange={(v) => update(i, { notes: v })} wide />
            </div>
          </div>
        ))}
      </section>

      <section className="card">
        <h3>Aus der Bibliothek hinzufügen</h3>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Übung oder Körperregion suchen …" />
        <div className="chips lib-chips">
          {library.length === 0 && <span className="muted">Keine Übungen gefunden. Die Bibliothek unter „Übungen“ füllen.</span>}
          {library.map((e) => (
            <button key={e.id} type="button" className="chip" onClick={() => add(e)}>
              + {e.title}
              {e.region && <span className="muted"> ({e.region})</span>}
            </button>
          ))}
        </div>
      </section>

      <ErrorBox error={error} />
      <div className="actions sticky-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Abbrechen
        </button>
        <button className="btn primary big" disabled={items.length === 0}>
          Speichern
        </button>
      </div>
    </form>
  );
}
