import { useRef, useState, type FormEvent } from "react";
import { api, apiUpload, type Exercise, type ExerciseData } from "../api";
import { useUser } from "../auth";
import { Check, ErrorBox, TextArea, TextField, useForm } from "../components/fields";
import Modal from "../components/Modal";
import { useApi } from "../hooks";

const BLANK: ExerciseData = { title: "", region: null, description: null, instructions: null, default_sets: 3, default_reps: 10, default_hold_seconds: null, contraindications: null };

export default function ExerciseLibraryPage() {
  const user = useUser();
  const [q, setQ] = useState("");
  const [archived, setArchived] = useState(false);
  const { data, error, reload } = useApi<Exercise[]>(`/exercises?${new URLSearchParams({ q, include_archived: String(archived) })}`);
  const [editing, setEditing] = useState<Exercise | "new" | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  async function seed() {
    setSeedError(null);
    try {
      await api("/exercises/seed-defaults", { method: "POST" });
      reload();
    } catch (e) {
      setSeedError((e as Error).message);
    }
  }

  const grouped = new Map<string, Exercise[]>();
  for (const e of data ?? []) grouped.set(e.region ?? "Ohne Region", [...(grouped.get(e.region ?? "Ohne Region") ?? []), e]);

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Übungsbibliothek</h1>
        <button className="btn primary" onClick={() => setEditing("new")}>
          + Neue Übung
        </button>
      </div>
      <input type="search" className="search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Übung oder Körperregion suchen …" />
      <label className="check">
        <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
        <span>Archivierte anzeigen</span>
      </label>
      <ErrorBox error={error ?? seedError} />

      {data && data.some((e) => !e.approved) && (
        <p className="ai-notice">
          Mitgelieferte Beispielübungen sind fachlich nicht geprüft. Bitte jede Übung durchsehen, Kontraindikationen ergänzen und freigeben. Erst freigegebene Übungen lassen sich in Übungsplänen drucken.
        </p>
      )}
      {data && data.length === 0 && !q && (
        <div className="card stack">
          <p>Die Bibliothek ist noch leer.</p>
          {user.role === "admin" ? (
            <button className="btn primary" onClick={seed}>
              {`Beispielübungen laden`}
            </button>
          ) : (
            <p className="muted">Ein Administrator kann Beispielübungen laden.</p>
          )}
        </div>
      )}

      {[...grouped.entries()].map(([region, list]) => (
        <section key={region} className="card">
          <h2>{region}</h2>
          <ul className="list">
            {list.map((e) => (
              <li key={e.id}>
                <button className="link-btn row-btn" onClick={() => setEditing(e)}>
                  {e.has_image ? <img className="mini" src={`/api/exercises/${e.id}/image`} alt="" loading="lazy" /> : <span className="mini empty" />}
                  <span>
                    <strong>{e.title}</strong>
                    {e.archived && <span className="badge">archiviert</span>}
                    {!e.approved && <span className="badge warn">nicht freigegeben</span>}
                    <span className="muted block">{e.description}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {editing && (
        <ExerciseDialog
          exercise={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function ExerciseDialog({ exercise, onClose, onSaved }: { exercise: Exercise | null; onClose: () => void; onSaved: () => void }) {
  const [e, set] = useForm<ExerciseData & { archived: boolean }>(exercise ? { ...exercise } : { ...BLANK, archived: false });
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [image, setImage] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const num = (v: string | null) => (v ? Math.max(1, Number(v) || 1) : null);

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    try {
      const body = { title: e.title, region: e.region, description: e.description, instructions: e.instructions, default_sets: e.default_sets, default_reps: e.default_reps, default_hold_seconds: e.default_hold_seconds, contraindications: e.contraindications, archived: e.archived };
      const saved = exercise ? await api<Exercise>(`/exercises/${exercise.id}`, { method: "PUT", body }) : await api<Exercise>("/exercises", { method: "POST", body });
      if (image) {
        const form = new FormData();
        form.set("file", image);
        await apiUpload(`/exercises/${saved.id}/image`, form);
      }
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Modal title={exercise ? "Übung bearbeiten" : "Neue Übung"} onClose={onClose} wide>
      <form className="form-grid" onSubmit={submit}>
        <TextField label="Titel" value={e.title} onChange={(v) => set("title", v ?? "")} required wide autoFocus />
        <TextField label="Körperregion" value={e.region} onChange={(v) => set("region", v)} placeholder="z. B. LWS, Schulter, Knie" />
        <TextField label="Sätze (Standard)" type="number" value={e.default_sets?.toString() ?? null} onChange={(v) => set("default_sets", num(v))} />
        <TextField label="Wiederholungen (Standard)" type="number" value={e.default_reps?.toString() ?? null} onChange={(v) => set("default_reps", num(v))} />
        <TextField label="Halten in Sekunden" type="number" value={e.default_hold_seconds?.toString() ?? null} onChange={(v) => set("default_hold_seconds", num(v))} />
        <TextArea label="Kurzbeschreibung (Ziel der Übung)" value={e.description} onChange={(v) => set("description", v)} rows={2} />
        <TextArea label="Anleitung für Patienten" value={e.instructions} onChange={(v) => set("instructions", v)} rows={5} />
        <TextArea label="Vorsicht / nicht geeignet bei (wird auf dem Übungsplan gedruckt)" value={e.contraindications} onChange={(v) => set("contraindications", v)} rows={2} />
        <div className="wide">
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(ev) => setImage(ev.target.files?.[0] ?? null)} />
          <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
            {image ? `Bild: ${image.name}` : exercise?.has_image ? "Bild ersetzen" : "Bild hinzufügen"}
          </button>
          <span className="muted"> Nur eigene oder lizenzfreie Bilder verwenden.</span>
        </div>
        {exercise && <Check label="Archiviert (nicht mehr zur Auswahl anbieten)" checked={e.archived} onChange={(v) => set("archived", v)} />}
        <div className="wide">
          <ErrorBox error={error} />
        </div>
        {exercise && (
          <p className="wide muted">
            {exercise.approved ? `✓ Fachlich freigegeben${exercise.approved_by ? ` von ${exercise.approved_by}` : ""}.` : "Noch nicht fachlich freigegeben – wird nicht gedruckt."}
          </p>
        )}
        <div className="actions wide">
          <button type="button" className="btn" onClick={onClose}>
            Abbrechen
          </button>
          {exercise && !exercise.approved && (
            <button
              type="button"
              className="btn"
              disabled={approving}
              onClick={async () => {
                setApproving(true);
                try {
                  await api(`/exercises/${exercise.id}/approve`, { method: "POST" });
                  onSaved();
                } catch (err) {
                  setError((err as Error).message);
                  setApproving(false);
                }
              }}
            >
              ✓ Fachlich freigeben
            </button>
          )}
          <button className="btn primary">Speichern</button>
        </div>
      </form>
    </Modal>
  );
}
