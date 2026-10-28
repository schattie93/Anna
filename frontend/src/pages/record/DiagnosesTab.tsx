import { useState, type FormEvent } from "react";
import { api, type Diagnosis, type DiagnosisData } from "../../api";
import { Check, ErrorBox, Select, TextArea, TextField, useForm } from "../../components/fields";
import { DIAGNOSIS_STATUS, SIDE, formatDate } from "../../labels";
import { Detail, EntryCard, TabHead, useVoidedToggle, type TabProps } from "./common";

const BLANK: DiagnosisData = {
  icd10_code: null,
  description: "",
  side: "none",
  diagnosed_on: null,
  diagnosed_by: null,
  is_primary: false,
  status: "active",
  notes: null,
};

export default function DiagnosesTab({ patientId, entries, reload }: TabProps<Diagnosis>) {
  const [editing, setEditing] = useState<Diagnosis | "new" | null>(null);
  const { showVoided, toggle } = useVoidedToggle();

  if (editing) {
    const entry = editing === "new" ? null : editing;
    return (
      <DiagnosisForm
        patientId={patientId}
        entry={entry}
        isFirst={entries.every((d) => d.voided)}
        onDone={() => {
          setEditing(null);
          reload();
        }}
        onCancel={() => setEditing(null)}
      />
    );
  }

  const visible = entries.filter((d) => showVoided || !d.voided);
  return (
    <div className="stack">
      <TabHead title="Diagnosen" newLabel="Neue Diagnose" onNew={() => setEditing("new")} />
      {visible.length === 0 && <p className="muted card">Noch keine Diagnose erfasst.</p>}
      {visible.map((d) => (
        <EntryCard
          key={d.id}
          entry={d}
          title={
            <>
              {d.icd10_code && <code className="icd">{d.icd10_code}</code>} {d.description}
            </>
          }
          badges={
            <>
              {d.is_primary && <span className="badge accent">Hauptdiagnose</span>}
              {d.status === "resolved" && <span className="badge">abgeschlossen</span>}
            </>
          }
          voidPath={`/patients/${patientId}/diagnoses/${d.id}/void`}
          onEdit={() => setEditing(d)}
          reload={reload}
        >
          <dl className="details">
            <Detail label="Seite" value={d.side !== "none" ? SIDE[d.side] : null} />
            <Detail label="Gestellt am" value={d.diagnosed_on && formatDate(d.diagnosed_on)} />
            <Detail label="Gestellt von" value={d.diagnosed_by} />
            <Detail label="Notizen" value={d.notes} />
          </dl>
        </EntryCard>
      ))}
      {entries.some((d) => d.voided) && toggle}
    </div>
  );
}

function DiagnosisForm({
  patientId,
  entry,
  isFirst,
  onDone,
  onCancel,
}: {
  patientId: number;
  entry: Diagnosis | null;
  isFirst: boolean;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [d, set] = useForm<DiagnosisData>(entry ?? { ...BLANK, is_primary: isFirst });
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (entry) await api(`/patients/${patientId}/diagnoses/${entry.id}`, { method: "PUT", body: d });
      else await api(`/patients/${patientId}/diagnoses`, { method: "POST", body: d });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <h2>{entry ? "Diagnose bearbeiten" : "Neue Diagnose"}</h2>
      <section className="card form-grid">
        <TextField label="Diagnose" value={d.description} onChange={(v) => set("description", v ?? "")} required wide autoFocus />
        <TextField label="ICD-10-Code" value={d.icd10_code} onChange={(v) => set("icd10_code", v)} placeholder="z. B. M54.5" />
        <Select label="Seite" value={d.side} options={SIDE} onChange={(v) => set("side", v)} />
        <TextField label="Gestellt am" type="date" value={d.diagnosed_on} onChange={(v) => set("diagnosed_on", v)} />
        <TextField label="Gestellt von" value={d.diagnosed_by} onChange={(v) => set("diagnosed_by", v)} placeholder="Ärztin/Arzt laut Verordnung" />
        <Select label="Status" value={d.status} options={DIAGNOSIS_STATUS} onChange={(v) => set("status", v)} />
        <div className="field">
          <span className="field-label">&nbsp;</span>
          <Check label="Hauptdiagnose" checked={d.is_primary} onChange={(v) => set("is_primary", v)} />
        </div>
        <TextArea label="Notizen" value={d.notes} onChange={(v) => set("notes", v)} />
      </section>
      <ErrorBox error={error} />
      <div className="actions sticky-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Abbrechen
        </button>
        <button className="btn primary big">Speichern</button>
      </div>
    </form>
  );
}
