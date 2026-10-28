import { useState, type FormEvent } from "react";
import { api, type Finding, type Goal, type GoalData, type Side } from "../../api";
import { ErrorBox, Field, Select, TextField, useForm } from "../../components/fields";
import LineChart from "../../components/LineChart";
import { GOAL_STATUS, SIDE, formatDate } from "../../labels";
import { EntryCard, TabHead, useVoidedToggle } from "./common";

const BLANK: GoalData = {
  description: "",
  target_date: null,
  status: "open",
  achieved_on: null,
  metric_name: null,
  metric_side: "none",
  baseline_value: null,
  target_value: null,
};

function seriesFor(goal: Goal, findings: Finding[]): Finding[] {
  if (!goal.metric_name) return [];
  return findings
    .filter((f) => !f.voided && f.name === goal.metric_name && f.side === goal.metric_side && f.value_num !== null)
    .sort((a, b) => a.recorded_on.localeCompare(b.recorded_on));
}

function progress(goal: Goal, series: Finding[]): number | null {
  if (goal.baseline_value === null || goal.target_value === null || series.length === 0 || goal.baseline_value === goal.target_value) return null;
  const latest = series[series.length - 1].value_num!;
  return Math.max(0, Math.min(1, (latest - goal.baseline_value) / (goal.target_value - goal.baseline_value)));
}

export default function GoalsTab({ patientId, entries, findings, reload }: { patientId: number; entries: Goal[]; findings: Finding[]; reload: () => void }) {
  const [editing, setEditing] = useState<Goal | "new" | null>(null);
  const { showVoided, toggle } = useVoidedToggle();

  if (editing) {
    return (
      <GoalForm
        patientId={patientId}
        entry={editing === "new" ? null : editing}
        findings={findings}
        onDone={() => {
          setEditing(null);
          reload();
        }}
        onCancel={() => setEditing(null)}
      />
    );
  }

  const visible = entries.filter((g) => showVoided || !g.voided);
  return (
    <div className="stack">
      <TabHead title="Therapieziele &amp; Zielerreichung" newLabel="Neues Ziel" onNew={() => setEditing("new")} />
      {visible.length === 0 && <p className="muted card">Noch keine Therapieziele.</p>}
      {visible.map((g) => {
        const series = seriesFor(g, findings);
        const pct = progress(g, series);
        return (
          <EntryCard
            key={g.id}
            entry={g}
            title={g.description}
            badges={<span className={g.status === "achieved" ? "badge ok" : g.status === "dropped" ? "badge" : "badge warn"}>{GOAL_STATUS[g.status]}</span>}
            voidPath={`/patients/${patientId}/goals/${g.id}/void`}
            onEdit={() => setEditing(g)}
            reload={reload}
          >
            <p className="muted">
              {g.target_date && <>Bis {formatDate(g.target_date)}. </>}
              {g.achieved_on && <>Erreicht am {formatDate(g.achieved_on)}. </>}
              {g.metric_name && (
                <>
                  Messgröße: {g.metric_name}
                  {g.metric_side !== "none" ? ` ${SIDE[g.metric_side]}` : ""} (Start {g.baseline_value ?? "–"} → Ziel {g.target_value ?? "–"}).
                </>
              )}
            </p>
            {pct !== null && (
              <div className="progress" role="progressbar" aria-valuenow={Math.round(pct * 100)} aria-valuemin={0} aria-valuemax={100}>
                <div style={{ width: `${pct * 100}%` }} />
                <span>{Math.round(pct * 100)} %</span>
              </div>
            )}
            {series.length >= 1 && g.target_value !== null && (
              <LineChart
                title={g.metric_name ?? ""}
                target={g.target_value}
                series={[{ label: g.metric_name ?? "", color: "#0f766e", points: series.map((f) => ({ date: f.recorded_on, value: f.value_num! })) }]}
              />
            )}
          </EntryCard>
        );
      })}
      {entries.some((g) => g.voided) && toggle}
    </div>
  );
}

function GoalForm({ patientId, entry, findings, onDone, onCancel }: { patientId: number; entry: Goal | null; findings: Finding[]; onDone: () => void; onCancel: () => void }) {
  const [g, set] = useForm<GoalData>(entry ?? BLANK);
  const [error, setError] = useState<string | null>(null);
  const metrics = [...new Map(findings.filter((f) => !f.voided && f.value_num !== null).map((f) => [`${f.name}|${f.side}`, f])).values()];
  const metricKey = g.metric_name ? `${g.metric_name}|${g.metric_side}` : "";
  const num = (v: string | null) => (v === null || v === "" ? null : Number(v.replace(",", ".")));

  function pickMetric(key: string) {
    if (!key) {
      set("metric_name", null);
      set("metric_side", "none");
      return;
    }
    const [name, side] = key.split("|");
    set("metric_name", name);
    set("metric_side", side as Side);
    const first = findings.filter((f) => !f.voided && f.name === name && f.side === side && f.value_num !== null).sort((a, b) => a.recorded_on.localeCompare(b.recorded_on))[0];
    if (first && g.baseline_value === null) set("baseline_value", first.value_num);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      if (entry) await api(`/patients/${patientId}/goals/${entry.id}`, { method: "PUT", body: g });
      else await api(`/patients/${patientId}/goals`, { method: "POST", body: g });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <h2>{entry ? "Therapieziel bearbeiten" : "Neues Therapieziel"}</h2>
      <section className="card form-grid">
        <TextField label="Ziel (Aktivität/Teilhabe)" value={g.description} onChange={(v) => set("description", v ?? "")} required wide autoFocus placeholder="z. B. 30 Minuten schmerzfrei spazieren gehen" />
        <TextField label="Zieldatum" type="date" value={g.target_date} onChange={(v) => set("target_date", v)} />
        <Select label="Status" value={g.status} options={GOAL_STATUS as Record<GoalData["status"], string>} onChange={(v) => set("status", v)} />
      </section>
      <section className="card form-grid">
        <h3 className="wide">Messbar machen (optional)</h3>
        <Field label="Messgröße aus den Befunden" wide>
          <select value={metricKey} onChange={(e) => pickMetric(e.target.value)}>
            <option value="">– keine –</option>
            {metrics.map((f) => (
              <option key={`${f.name}|${f.side}`} value={`${f.name}|${f.side}`}>
                {f.name}
                {f.side !== "none" ? ` ${SIDE[f.side]}` : ""} {f.unit ? `(${f.unit})` : ""}
              </option>
            ))}
          </select>
        </Field>
        {g.metric_name && (
          <>
            <TextField label="Ausgangswert" value={g.baseline_value?.toString() ?? null} onChange={(v) => set("baseline_value", num(v))} />
            <TextField label="Zielwert" value={g.target_value?.toString() ?? null} onChange={(v) => set("target_value", num(v))} />
          </>
        )}
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

