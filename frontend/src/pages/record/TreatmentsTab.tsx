import { useState } from "react";
import { api, type Catalog, type Diagnosis, type Prescription, type Treatment, type TreatmentData } from "../../api";
import { Chips, ErrorBox, Field, PainScale, ReasonDialog, TextArea, TextField, useForm } from "../../components/fields";
import { formatDate, formatDateTime, today } from "../../labels";
import { Detail, EntryCard, TabHead, useVoidedToggle, type TabProps } from "./common";

function blank(previous: Treatment | undefined, diagnoses: Diagnosis[], prescriptions: Prescription[]): TreatmentData {
  const primary = diagnoses.find((d) => d.is_primary && !d.voided);
  return {
    treated_on: today(),
    diagnosis_id: previous?.diagnosis_id ?? primary?.id ?? null,
    prescription_id: prescriptions.find((r) => !r.voided && r.status === "open")?.id ?? null,
    duration_minutes: previous?.duration_minutes ?? null,
    measures: [],
    subjective: null,
    objective: null,
    assessment: null,
    plan: null,
    pain_before: null,
    pain_after: null,
    home_exercises: null,
  };
}

export default function TreatmentsTab({
  patientId,
  catalog,
  entries,
  diagnoses,
  prescriptions,
  reload,
}: TabProps<Treatment> & { diagnoses: Diagnosis[]; prescriptions: Prescription[] }) {
  const [editing, setEditing] = useState<Treatment | "new" | null>(null);
  const { showVoided, toggle } = useVoidedToggle();
  const previous = entries.find((t) => !t.voided);

  if (editing) {
    return (
      <TreatmentForm
        patientId={patientId}
        catalog={catalog}
        diagnoses={diagnoses}
        prescriptions={prescriptions}
        entry={editing === "new" ? null : editing}
        previous={editing === "new" ? previous : undefined}
        onDone={() => {
          setEditing(null);
          reload();
        }}
        onCancel={() => setEditing(null)}
      />
    );
  }

  const visible = entries.filter((t) => showVoided || !t.voided);
  const diagnosisName = (id: number | null) => diagnoses.find((d) => d.id === id)?.description;
  const rxLabel = (id: number | null) => {
    const r = prescriptions.find((x) => x.id === id);
    return r ? `${r.measure} vom ${formatDate(r.issued_on)} (${r.units_done}/${r.total_units})` : null;
  };

  return (
    <div className="stack">
      <TabHead title="Behandlungen" newLabel="Neue Behandlung" onNew={() => setEditing("new")} />
      {visible.length === 0 && <p className="muted card">Noch keine Behandlung dokumentiert.</p>}
      {visible.map((t, i) => (
        <EntryCard
          key={t.id}
          entry={t}
          title={`${visible.length - i}. Behandlung · ${formatDate(t.treated_on)}`}
          badges={
            t.status === "draft" ? (
              <span className="badge warn">Entwurf</span>
            ) : (
              <span className="badge ok" title={t.finalized_at ? `abgeschlossen ${formatDateTime(t.finalized_at)}` : ""}>
                abgeschlossen
              </span>
            )
          }
          voidPath={`/patients/${patientId}/treatments/${t.id}/void`}
          onEdit={() => setEditing(t)}
          reload={reload}
        >
          <dl className="details">
            <Detail label="Diagnose" value={diagnosisName(t.diagnosis_id)} />
            <Detail label="Verordnung" value={rxLabel(t.prescription_id)} />
            <Detail label="Dauer" value={t.duration_minutes && `${t.duration_minutes} min`} />
            <Detail label="Maßnahmen" value={t.measures.join(", ")} />
            <Detail
              label="Schmerz (NRS)"
              value={t.pain_before !== null || t.pain_after !== null ? `vorher ${t.pain_before ?? "–"} → nachher ${t.pain_after ?? "–"}` : null}
            />
            <Detail label="S – Subjektiv" value={t.subjective} />
            <Detail label="O – Objektiv" value={t.objective} />
            <Detail label="A – Beurteilung" value={t.assessment} />
            <Detail label="P – Plan" value={t.plan} />
            <Detail label="Hausübungen" value={t.home_exercises} />
          </dl>
        </EntryCard>
      ))}
      {entries.some((t) => t.voided) && toggle}
    </div>
  );
}

function TreatmentForm({
  patientId,
  catalog,
  diagnoses,
  prescriptions,
  entry,
  previous,
  onDone,
  onCancel,
}: {
  patientId: number;
  catalog: Catalog;
  diagnoses: Diagnosis[];
  prescriptions: Prescription[];
  entry: Treatment | null;
  previous: Treatment | undefined;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [t, set, setAll] = useForm<TreatmentData>(entry ?? blank(previous, diagnoses, prescriptions));
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ finalize: boolean } | null>(null);
  const isFinal = entry?.status === "final";
  const measureOptions = Object.fromEntries([...catalog.measures, ...t.measures].map((m) => [m, m]));
  const activeDiagnoses = diagnoses.filter((d) => !d.voided || d.id === t.diagnosis_id);

  async function save(finalize: boolean, correction_reason?: string) {
    setError(null);
    try {
      const body = { ...t, finalize, correction_reason };
      if (entry) await api(`/patients/${patientId}/treatments/${entry.id}`, { method: "PUT", body });
      else await api(`/patients/${patientId}/treatments`, { method: "POST", body });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function trigger(finalize: boolean) {
    if (isFinal) setPending({ finalize });
    else save(finalize);
  }

  // Bewusste Übernahme: Maßnahmen, Plan und Hausübungen der letzten Behandlung in den Entwurf kopieren
  function copyPrevious() {
    if (!previous) return;
    setAll({
      ...t,
      measures: previous.measures,
      plan: previous.plan,
      home_exercises: previous.home_exercises,
      duration_minutes: previous.duration_minutes,
      diagnosis_id: previous.diagnosis_id,
    });
  }

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        trigger(false);
      }}
    >
      <div className="page-head">
        <h2>{entry ? (isFinal ? "Abgeschlossene Behandlung korrigieren" : "Behandlung bearbeiten") : "Neue Behandlung"}</h2>
        {previous && !entry && (
          <button type="button" className="btn" onClick={copyPrevious}>
            ↺ Werte vom {formatDate(previous.treated_on)} übernehmen
          </button>
        )}
      </div>

      <section className="card form-grid">
        <TextField label="Datum" type="date" value={t.treated_on} onChange={(v) => set("treated_on", v ?? "")} required />
        <TextField
          label="Dauer (Minuten)"
          type="number"
          value={t.duration_minutes?.toString() ?? null}
          onChange={(v) => set("duration_minutes", v ? Number(v) : null)}
        />
        <Field label="Diagnose" wide>
          <select value={t.diagnosis_id ?? ""} onChange={(e) => set("diagnosis_id", e.target.value ? Number(e.target.value) : null)}>
            <option value="">– keine Zuordnung –</option>
            {activeDiagnoses.map((d) => (
              <option key={d.id} value={d.id}>
                {d.icd10_code ? `${d.icd10_code} – ` : ""}
                {d.description}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Verordnung" wide>
          <select value={t.prescription_id ?? ""} onChange={(e) => set("prescription_id", e.target.value ? Number(e.target.value) : null)}>
            <option value="">– keine Zuordnung –</option>
            {prescriptions
              .filter((r) => !r.voided && (r.status === "open" || r.id === t.prescription_id))
              .map((r) => (
                <option key={r.id} value={r.id}>
                  {r.measure} vom {formatDate(r.issued_on)} ({r.units_done}/{r.total_units} Einheiten)
                </option>
              ))}
          </select>
        </Field>
        <Chips label="Maßnahmen" options={measureOptions} value={t.measures} onChange={(v) => set("measures", v)} />
      </section>

      <section className="card form-grid">
        <PainScale label="Schmerz vor der Behandlung (NRS)" value={t.pain_before} onChange={(v) => set("pain_before", v)} />
        <TextArea label="S – Subjektiv (Befinden, Rückmeldung seit letzter Behandlung)" value={t.subjective} onChange={(v) => set("subjective", v)} />
        <TextArea label="O – Objektiv (Befund, Tests, Messwerte)" value={t.objective} onChange={(v) => set("objective", v)} />
        <TextArea label="A – Beurteilung (Reaktion, Fortschritt)" value={t.assessment} onChange={(v) => set("assessment", v)} />
        <TextArea label="P – Plan (nächste Schritte)" value={t.plan} onChange={(v) => set("plan", v)} />
        <PainScale label="Schmerz nach der Behandlung (NRS)" value={t.pain_after} onChange={(v) => set("pain_after", v)} />
        <TextArea label="Hausübungen" value={t.home_exercises} onChange={(v) => set("home_exercises", v)} rows={2} />
      </section>

      <ErrorBox error={error} />
      <div className="actions sticky-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Abbrechen
        </button>
        {isFinal ? (
          <button className="btn primary big">Korrektur speichern</button>
        ) : (
          <>
            <button className="btn big">Als Entwurf speichern</button>
            <button type="button" className="btn primary big" onClick={() => trigger(true)}>
              ✓ Abschließen
            </button>
          </>
        )}
      </div>
      {pending && (
        <ReasonDialog
          title="Grund der Korrektur"
          confirmLabel="Korrektur speichern"
          onConfirm={(r) => {
            const { finalize } = pending;
            setPending(null);
            save(finalize, r);
          }}
          onCancel={() => setPending(null)}
        />
      )}
    </form>
  );
}
