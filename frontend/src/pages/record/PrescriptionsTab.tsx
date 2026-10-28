import { useState, type FormEvent } from "react";
import { api, type Prescription, type PrescriptionData } from "../../api";
import { Check, ErrorBox, Field, TextArea, TextField, useForm } from "../../components/fields";
import { RX_STATUS, formatDate, today } from "../../labels";
import { Detail, EntryCard, TabHead, useVoidedToggle, type TabProps } from "./common";

const MEASURES = ["Krankengymnastik (KG)", "KG am Gerät (KGG)", "KG-ZNS (Bobath/PNF)", "Manuelle Therapie (MT)", "Manuelle Lymphdrainage (MLD)", "Klassische Massage (KMT)", "Wärmetherapie", "Elektrotherapie"];

export default function PrescriptionsTab({ patientId, entries, reload, defaultPhysician }: Omit<TabProps<Prescription>, "catalog"> & { defaultPhysician: string | null }) {
  const [editing, setEditing] = useState<Prescription | "new" | null>(null);
  const { showVoided, toggle } = useVoidedToggle();

  if (editing) {
    return (
      <RxForm
        patientId={patientId}
        entry={editing === "new" ? null : editing}
        defaultPhysician={defaultPhysician}
        onDone={() => {
          setEditing(null);
          reload();
        }}
        onCancel={() => setEditing(null)}
      />
    );
  }

  const visible = entries.filter((r) => showVoided || !r.voided);
  return (
    <div className="stack">
      <TabHead title="Verordnungen" newLabel="Neue Verordnung" onNew={() => setEditing("new")} />
      {visible.length === 0 && <p className="muted card">Noch keine Verordnung erfasst.</p>}
      {visible.map((r) => (
        <EntryCard
          key={r.id}
          entry={r}
          title={`${r.measure} · ${r.total_units} Einheiten · vom ${formatDate(r.issued_on)}`}
          badges={
            <>
              <span className={r.status === "open" ? "badge accent" : r.status === "expired" ? "badge danger" : "badge"}>{RX_STATUS[r.status]}</span>
              {r.urgent && <span className="badge warn">dringlich</span>}
              {r.home_visit && <span className="badge">Hausbesuch</span>}
            </>
          }
          voidPath={`/patients/${patientId}/prescriptions/${r.id}/void`}
          onEdit={() => setEditing(r)}
          reload={reload}
        >
          <div className="progress" role="progressbar" aria-valuenow={r.units_done} aria-valuemin={0} aria-valuemax={r.total_units}>
            <div style={{ width: `${Math.min(100, (r.units_done / r.total_units) * 100)}%` }} />
            <span>
              {r.units_done} von {r.total_units} Einheiten
            </span>
          </div>
          {r.warnings.length > 0 && (
            <ul className="rx-warnings">
              {r.warnings.map((w) => (
                <li key={w.text} className={w.level}>
                  {w.level === "warn" ? "⚠ " : "ℹ "}
                  {w.text}
                </li>
              ))}
            </ul>
          )}
          <dl className="details">
            <Detail label="Verordner/in" value={r.physician} />
            <Detail label="Diagnose" value={[r.icd10_code, r.diagnosis_text].filter(Boolean).join(" – ")} />
            <Detail label="Indikationsschlüssel" value={r.indication_key} />
            <Detail label="Frequenz" value={r.frequency} />
            <Detail label="Beginn spätestens" value={r.latest_start && formatDate(r.latest_start)} />
            <Detail label="Notizen" value={r.notes} />
          </dl>
        </EntryCard>
      ))}
      {entries.some((r) => r.voided) && toggle}
    </div>
  );
}

function RxForm({ patientId, entry, defaultPhysician, onDone, onCancel }: { patientId: number; entry: Prescription | null; defaultPhysician: string | null; onDone: () => void; onCancel: () => void }) {
  const initial: PrescriptionData = entry ?? {
    issued_on: today(),
    physician: defaultPhysician,
    diagnosis_text: null,
    icd10_code: null,
    indication_key: null,
    measure: "",
    total_units: 6,
    frequency: null,
    urgent: false,
    home_visit: false,
    notes: null,
  };
  const [r, set] = useForm<PrescriptionData>(initial);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (entry) await api(`/patients/${patientId}/prescriptions/${entry.id}`, { method: "PUT", body: r });
      else await api(`/patients/${patientId}/prescriptions`, { method: "POST", body: r });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <h2>{entry ? "Verordnung bearbeiten" : "Neue Verordnung"}</h2>
      <section className="card form-grid">
        <TextField label="Ausstellungsdatum" type="date" value={r.issued_on} onChange={(v) => set("issued_on", v ?? "")} required autoFocus />
        <TextField label="Verordnende/r Ärztin/Arzt" value={r.physician} onChange={(v) => set("physician", v)} />
        <Field label="Heilmittel *">
          <input list="rx-measures" value={r.measure} required onChange={(e) => set("measure", e.target.value)} />
          <datalist id="rx-measures">
            {MEASURES.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </Field>
        <TextField
          label="Anzahl Einheiten"
          type="number"
          value={String(r.total_units)}
          onChange={(v) => set("total_units", Math.max(1, Number(v) || 1))}
          required
        />
        <TextField label="Frequenz" value={r.frequency} onChange={(v) => set("frequency", v)} placeholder="z. B. 2x pro Woche" />
        <TextField label="Indikationsschlüssel" value={r.indication_key} onChange={(v) => set("indication_key", v)} placeholder="z. B. WS1" />
        <TextField label="ICD-10" value={r.icd10_code} onChange={(v) => set("icd10_code", v)} />
        <TextField label="Diagnose laut Verordnung" value={r.diagnosis_text} onChange={(v) => set("diagnosis_text", v)} wide />
        <div className="wide checks">
          <Check label="Dringlicher Behandlungsbedarf (kürzere Beginn-Frist)" checked={r.urgent} onChange={(v) => set("urgent", v)} />
          <Check label="Hausbesuch" checked={r.home_visit} onChange={(v) => set("home_visit", v)} />
        </div>
        <TextArea label="Notizen" value={r.notes} onChange={(v) => set("notes", v)} rows={2} />
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
