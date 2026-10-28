import { useState, type FormEvent } from "react";
import { api, type Examination, type ExaminationData } from "../../api";
import { ErrorBox, ReasonDialog, TextArea, TextField, useForm } from "../../components/fields";
import { formatDate, today } from "../../labels";
import { Detail, EntryCard, TabHead, useVoidedToggle } from "./common";

const BLANK: ExaminationData = {
  recorded_on: today(),
  inspection: null,
  palpation: null,
  function: null,
  hypothesis: null,
  icf_body: null,
  icf_activity: null,
  icf_participation: null,
  notes: null,
};

export default function ExaminationTab({ patientId, entries, reload }: { patientId: number; entries: Examination[]; reload: () => void }) {
  const [editing, setEditing] = useState<Examination | "new" | null>(null);
  const { showVoided, toggle } = useVoidedToggle();

  if (editing) {
    return (
      <ExaminationForm
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

  const visible = entries.filter((e) => showVoided || !e.voided);
  return (
    <div className="stack">
      <TabHead title="Erstbefund / Untersuchung" newLabel="Neuer Befund" onNew={() => setEditing("new")} />
      <p className="muted">Strukturierte Untersuchung. Messwerte und Tests tragen Sie im Reiter „Befunde“ ein, damit sie im Verlauf ausgewertet werden.</p>
      {visible.length === 0 && <p className="muted card">Noch kein Erstbefund erfasst.</p>}
      {visible.map((e) => (
        <EntryCard key={e.id} entry={e} title={`Untersuchung vom ${formatDate(e.recorded_on)}`} voidPath={`/patients/${patientId}/examinations/${e.id}/void`} onEdit={() => setEditing(e)} reload={reload}>
          <dl className="details">
            <Detail label="Inspektion" value={e.inspection} />
            <Detail label="Palpation" value={e.palpation} />
            <Detail label="Funktionsprüfung" value={e.function} />
            <Detail label="Hypothese / Beurteilung" value={e.hypothesis} />
            <Detail label="ICF Körperfunktion/-struktur" value={e.icf_body} />
            <Detail label="ICF Aktivität" value={e.icf_activity} />
            <Detail label="ICF Teilhabe" value={e.icf_participation} />
            <Detail label="Notizen" value={e.notes} />
          </dl>
        </EntryCard>
      ))}
      {entries.some((e) => e.voided) && toggle}
    </div>
  );
}

function ExaminationForm({ patientId, entry, onDone, onCancel }: { patientId: number; entry: Examination | null; onDone: () => void; onCancel: () => void }) {
  const [e, set] = useForm<ExaminationData>(entry ?? BLANK);
  const [error, setError] = useState<string | null>(null);
  const [askReason, setAskReason] = useState(false);

  async function save(correction_reason?: string) {
    setError(null);
    try {
      if (entry) await api(`/patients/${patientId}/examinations/${entry.id}`, { method: "PUT", body: { ...e, correction_reason } });
      else await api(`/patients/${patientId}/examinations`, { method: "POST", body: e });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function submit(ev: FormEvent) {
    ev.preventDefault();
    if (entry) setAskReason(true);
    else save();
  }

  return (
    <form className="stack" onSubmit={submit}>
      <h2>{entry ? "Untersuchung korrigieren" : "Neue Untersuchung"}</h2>
      <section className="card form-grid">
        <TextField label="Datum" type="date" value={e.recorded_on} onChange={(v) => set("recorded_on", v ?? "")} required />
        <TextArea label="Inspektion (Haltung, Schonhaltung, Schwellung, Hautzustand, Gang)" value={e.inspection} onChange={(v) => set("inspection", v)} rows={3} />
        <TextArea label="Palpation (Tonus, Druckschmerz, Temperatur, Gewebe)" value={e.palpation} onChange={(v) => set("palpation", v)} rows={3} />
        <TextArea label="Funktionsprüfung (aktive/passive Bewegung, Widerstandstests, Bewegungsanalyse)" value={e.function} onChange={(v) => set("function", v)} rows={4} />
      </section>
      <section className="card form-grid">
        <h3 className="wide">Beurteilung und ICF-Einordnung</h3>
        <TextArea label="Physiotherapeutische Hypothese / Beurteilung" value={e.hypothesis} onChange={(v) => set("hypothesis", v)} rows={3} />
        <TextArea label="Körperfunktionen und -strukturen (z. B. Beweglichkeit, Kraft, Schmerz)" value={e.icf_body} onChange={(v) => set("icf_body", v)} rows={2} />
        <TextArea label="Aktivitäten (was kann der Patient nicht mehr tun?)" value={e.icf_activity} onChange={(v) => set("icf_activity", v)} rows={2} />
        <TextArea label="Teilhabe (Beruf, Familie, Freizeit)" value={e.icf_participation} onChange={(v) => set("icf_participation", v)} rows={2} />
        <TextArea label="Notizen" value={e.notes} onChange={(v) => set("notes", v)} rows={2} />
      </section>
      <ErrorBox error={error} />
      <div className="actions sticky-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Abbrechen
        </button>
        <button className="btn primary big">Speichern</button>
      </div>
      {askReason && (
        <ReasonDialog
          title="Grund der Korrektur"
          confirmLabel="Korrektur speichern"
          onConfirm={(r) => {
            setAskReason(false);
            save(r);
          }}
          onCancel={() => setAskReason(false)}
        />
      )}
    </form>
  );
}
