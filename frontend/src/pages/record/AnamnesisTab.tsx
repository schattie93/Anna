import { useState, type FormEvent } from "react";
import { api, type Anamnesis, type AnamnesisData, type Catalog } from "../../api";
import { Chips, ErrorBox, PainScale, ReasonDialog, TextArea, TextField, useForm } from "../../components/fields";
import { formatDate, today } from "../../labels";
import { Detail, EntryCard, TabHead, useVoidedToggle, type TabProps } from "./common";

function blank(): AnamnesisData {
  return {
    recorded_on: today(),
    chief_complaint: "",
    onset: null,
    current_history: null,
    past_history: null,
    surgeries: null,
    medication: null,
    pain_current: null,
    pain_max: null,
    pain_character: null,
    aggravating_factors: null,
    relieving_factors: null,
    red_flags: [],
    red_flags_notes: null,
    yellow_flags: [],
    social_history: null,
    sleep: null,
    activity_sport: null,
    goals: null,
  };
}

export default function AnamnesisTab({ patientId, catalog, entries, reload }: TabProps<Anamnesis>) {
  const [editing, setEditing] = useState<Anamnesis | "new" | null>(null);
  const { showVoided, toggle } = useVoidedToggle();

  if (editing) {
    return (
      <AnamnesisForm
        patientId={patientId}
        catalog={catalog}
        entry={editing === "new" ? null : editing}
        onDone={() => {
          setEditing(null);
          reload();
        }}
        onCancel={() => setEditing(null)}
      />
    );
  }

  const visible = entries.filter((a) => showVoided || !a.voided);
  return (
    <div className="stack">
      <TabHead title="Anamnese" newLabel="Neue Anamnese" onNew={() => setEditing("new")} />
      {visible.length === 0 && <p className="muted card">Noch keine Anamnese erfasst.</p>}
      {visible.map((a) => (
        <EntryCard
          key={a.id}
          entry={a}
          title={`Anamnese vom ${formatDate(a.recorded_on)}`}
          voidPath={`/patients/${patientId}/anamneses/${a.id}/void`}
          onEdit={() => setEditing(a)}
          reload={reload}
        >
          <AnamnesisView a={a} catalog={catalog} />
        </EntryCard>
      ))}
      {entries.some((a) => a.voided) && toggle}
    </div>
  );
}

export function AnamnesisView({ a, catalog }: { a: Anamnesis; catalog: Catalog }) {
  return (
    <dl className="details">
      <Detail label="Hauptbeschwerde" value={a.chief_complaint} />
      <Detail label="Beginn / Auslöser" value={a.onset} />
      <Detail label="Aktuelle Anamnese" value={a.current_history} />
      <Detail label="Schmerz aktuell (NRS)" value={a.pain_current} />
      <Detail label="Schmerz maximal (NRS)" value={a.pain_max} />
      <Detail label="Schmerzcharakter" value={a.pain_character} />
      <Detail label="Verstärkend" value={a.aggravating_factors} />
      <Detail label="Lindernd" value={a.relieving_factors} />
      <Detail label="Vorerkrankungen" value={a.past_history} />
      <Detail label="Operationen" value={a.surgeries} />
      <Detail label="Medikamente" value={a.medication} />
      <Detail
        label="Warnzeichen"
        value={
          a.red_flags.length > 0 && (
            <span className="danger-text">⚠ {a.red_flags.map((f) => catalog.red_flags[f] ?? f).join(", ")}</span>
          )
        }
      />
      <Detail label="Anmerkung Warnzeichen" value={a.red_flags_notes} />
      <Detail label="Psychosoziale Faktoren" value={a.yellow_flags.length > 0 && a.yellow_flags.map((f) => catalog.yellow_flags[f] ?? f).join(", ")} />
      <Detail label="Sozialanamnese" value={a.social_history} />
      <Detail label="Schlaf" value={a.sleep} />
      <Detail label="Alltag / Sport" value={a.activity_sport} />
      <Detail label="Therapieziele" value={a.goals} />
    </dl>
  );
}

function AnamnesisForm({
  patientId,
  catalog,
  entry,
  onDone,
  onCancel,
}: {
  patientId: number;
  catalog: Catalog;
  entry: Anamnesis | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [a, set] = useForm<AnamnesisData>(entry ?? blank());
  const [error, setError] = useState<string | null>(null);
  const [askReason, setAskReason] = useState(false);

  async function save(correction_reason?: string) {
    setError(null);
    try {
      if (entry) {
        await api(`/patients/${patientId}/anamneses/${entry.id}`, { method: "PUT", body: { ...a, correction_reason } });
      } else {
        await api(`/patients/${patientId}/anamneses`, { method: "POST", body: a });
      }
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (entry) setAskReason(true);
    else save();
  }

  return (
    <form className="stack" onSubmit={submit}>
      <h2>{entry ? "Anamnese korrigieren" : "Neue Anamnese"}</h2>
      <section className="card form-grid">
        <TextField label="Datum" type="date" value={a.recorded_on} onChange={(v) => set("recorded_on", v ?? "")} required />
        <TextArea label="Hauptbeschwerde" value={a.chief_complaint} onChange={(v) => set("chief_complaint", v ?? "")} required rows={2} />
        <TextArea label="Beginn / Auslöser" value={a.onset} onChange={(v) => set("onset", v)} rows={2} placeholder="Seit wann? Ereignis, Unfall, schleichend …" />
        <TextArea label="Aktuelle Anamnese / Verlauf" value={a.current_history} onChange={(v) => set("current_history", v)} />
      </section>

      <section className="card form-grid">
        <h3 className="wide">Schmerz</h3>
        <PainScale label="Schmerz aktuell (NRS 0–10)" value={a.pain_current} onChange={(v) => set("pain_current", v)} />
        <PainScale label="Schmerz maximal (NRS 0–10)" value={a.pain_max} onChange={(v) => set("pain_max", v)} />
        <TextArea label="Schmerzcharakter" value={a.pain_character} onChange={(v) => set("pain_character", v)} rows={2} placeholder="stechend, ziehend, brennend, ausstrahlend …" />
        <TextArea label="Verstärkende Faktoren" value={a.aggravating_factors} onChange={(v) => set("aggravating_factors", v)} rows={2} />
        <TextArea label="Lindernde Faktoren" value={a.relieving_factors} onChange={(v) => set("relieving_factors", v)} rows={2} />
      </section>

      <section className="card form-grid">
        <h3 className="wide">Warnzeichen (Red Flags)</h3>
        <Chips label="Zutreffendes antippen" options={catalog.red_flags} value={a.red_flags} onChange={(v) => set("red_flags", v)} tone="warn" />
        <TextArea label="Anmerkungen zu Warnzeichen" value={a.red_flags_notes} onChange={(v) => set("red_flags_notes", v)} rows={2} />
      </section>

      <section className="card form-grid">
        <h3 className="wide">Psychosoziale Faktoren (Yellow Flags) und Alltag</h3>
        <Chips label="Zutreffendes antippen (Hinweise auf Chronifizierungsrisiko)" options={catalog.yellow_flags} value={a.yellow_flags} onChange={(v) => set("yellow_flags", v)} />
        <TextArea label="Sozialanamnese (Beruf, Familie, Wohnsituation, Belastungen)" value={a.social_history} onChange={(v) => set("social_history", v)} rows={2} />
        <TextArea label="Schlaf" value={a.sleep} onChange={(v) => set("sleep", v)} rows={2} />
      </section>

      <section className="card form-grid">
        <h3 className="wide">Vorgeschichte</h3>
        <TextArea label="Vorerkrankungen" value={a.past_history} onChange={(v) => set("past_history", v)} rows={2} />
        <TextArea label="Operationen" value={a.surgeries} onChange={(v) => set("surgeries", v)} rows={2} />
        <TextArea label="Medikamente" value={a.medication} onChange={(v) => set("medication", v)} rows={2} />
        <TextArea label="Alltag, Beruf, Sport" value={a.activity_sport} onChange={(v) => set("activity_sport", v)} rows={2} />
        <TextArea label="Therapieziele" value={a.goals} onChange={(v) => set("goals", v)} rows={2} placeholder="Was möchte der Patient wieder können?" />
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
