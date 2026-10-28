import { useMemo, useState, type FormEvent } from "react";
import { api, type Finding, type FindingCategory, type FindingData, type Side } from "../../api";
import { ErrorBox, Field, ReasonDialog, Select, TextField } from "../../components/fields";
import LineChart from "../../components/LineChart";
import { CATEGORY, SIDE, formatDate, today } from "../../labels";
import { type TabProps } from "./common";

const TEAL = "#0f766e";

const fmt = (n: number | null) => String(n ?? "–").replace(".", ",");

/** Neutral-Null-Methode: "Gegenrichtung-Neutral-Hauptrichtung", z. B. 0-0-130. */
function pairLabels(name: string): [string, string] | null {
  const m = name.match(/\(([^/()]+)\/([^()]+)\)\s*$/);
  return m ? [m[1].trim(), m[2].trim()] : null;
}

function show(f: Finding): string {
  if (f.category === "test") return f.value_text ?? "–";
  const unit = f.unit ? " " + f.unit : "";
  if (f.value_opposite !== null) return `${fmt(f.value_opposite)}-${fmt(f.value_neutral ?? 0)}-${fmt(f.value_num)}${unit}`;
  return `${fmt(f.value_num)}${unit}`;
}

const num = (v: string): number => Number(v.replace(",", "."));

export default function FindingsTab({ patientId, catalog, entries, reload }: TabProps<Finding>) {
  const [category, setCategory] = useState<FindingCategory>("rom");
  const [date, setDate] = useState(today());
  const [name, setName] = useState("");
  const [side, setSide] = useState<Side>("none");
  const [value, setValue] = useState("");
  const [opposite, setOpposite] = useState("");
  const [neutral, setNeutral] = useState("0");
  const [result, setResult] = useState<string | null>(null);
  const [unit, setUnit] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lastAdded, setLastAdded] = useState<string | null>(null);
  const [filter, setFilter] = useState<FindingCategory | "all">("all");

  const presets = catalog.finding_presets.filter((p) => p.category === category);
  const labels = category === "rom" ? pairLabels(name) : null;
  const preset = presets.find((p) => p.name === name);
  const norm = labels ? preset?.norm ?? undefined : undefined;

  function pickName(v: string) {
    setName(v);
    const preset = presets.find((p) => p.name === v);
    if (preset) setUnit(preset.unit ?? "");
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const body: FindingData = {
      recorded_on: date,
      category,
      name: name.trim(),
      side,
      value_num: category === "test" ? null : num(value),
      value_opposite: labels ? num(opposite) : null,
      value_neutral: labels ? num(neutral || "0") : null,
      value_text: category === "test" ? result : null,
      unit: category === "test" ? null : unit.trim() || null,
      notes: notes.trim() || null,
      treatment_id: null,
    };
    if (category !== "test" && Number.isNaN(body.value_num)) return setError("Bitte einen Zahlenwert eingeben");
    if (labels && (Number.isNaN(body.value_opposite) || Number.isNaN(body.value_neutral))) return setError("Bitte alle drei Werte eingeben (Neutral-Null-Methode)");
    try {
      await api(`/patients/${patientId}/findings`, { method: "POST", body });
      setLastAdded(`${body.name}${body.side !== "none" ? " " + SIDE[body.side] : ""}`);
      setValue("");
      setOpposite("");
      setNeutral("0");
      setResult(null);
      setNotes("");
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const groups = useMemo(() => {
    const map = new Map<string, Finding[]>();
    for (const f of entries.filter((x) => !x.voided && (filter === "all" || x.category === filter))) {
      const key = `${f.category}|${f.name}|${f.side}`;
      map.set(key, [...(map.get(key) ?? []), f]);
    }
    return [...map.values()].map((g) => g.sort((a, b) => a.recorded_on.localeCompare(b.recorded_on) || a.id - b.id));
  }, [entries, filter]);

  return (
    <div className="stack">
      <h2>Befunde &amp; Messwerte</h2>

      <form className="card form-grid" onSubmit={add}>
        <div className="field wide">
          <span className="field-label">Art</span>
          <div className="chips">
            {(Object.keys(CATEGORY) as FindingCategory[]).map((c) => (
              <button
                key={c}
                type="button"
                aria-pressed={category === c}
                className={category === c ? "chip on" : "chip"}
                onClick={() => {
                  setCategory(c);
                  setName("");
                  setUnit("");
                  setResult(null);
                }}
              >
                {CATEGORY[c]}
              </button>
            ))}
          </div>
        </div>
        <TextField label="Datum" type="date" value={date} onChange={(v) => setDate(v ?? "")} required />
        <Field label="Befund *">
          <input list="finding-presets" value={name} required onChange={(e) => pickName(e.target.value)} placeholder="auswählen oder eigene Bezeichnung" />
          <datalist id="finding-presets">
            {presets.map((p) => (
              <option key={p.name} value={p.name} />
            ))}
          </datalist>
        </Field>
        <Select label="Seite" value={side} options={SIDE as Record<Side, string>} onChange={setSide} />
        {category === "test" ? (
          <div className="field wide">
            <span className="field-label">Ergebnis *</span>
            <div className="chips">
              {catalog.test_results.map((r) => (
                <button key={r} type="button" aria-pressed={result === r} className={result === r ? (r === "positiv" ? "chip on warn" : "chip on") : "chip"} onClick={() => setResult(r)}>
                  {r}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {labels ? (
              <div className="field wide">
                <span className="field-label">Neutral-Null-Methode: {labels[0]} – Neutral – {labels[1]} *</span>
                <div className="neutral-null">
                  <input aria-label={labels[0]} inputMode="decimal" placeholder={labels[0]} value={opposite} required onChange={(e) => setOpposite(e.target.value)} />
                  <span>–</span>
                  <input aria-label="Neutral" inputMode="decimal" placeholder="Neutral" value={neutral} required onChange={(e) => setNeutral(e.target.value)} />
                  <span>–</span>
                  <input aria-label={labels[1]} inputMode="decimal" placeholder={labels[1]} value={value} required onChange={(e) => setValue(e.target.value)} />
                </div>
                {norm && (
                  <span className="field-hint">
                    Richtwert{preset?.reviewed ? " (Praxis)" : " (ungeprüft, bitte mit Ihrer Quelle abgleichen)"}: {norm[0]}-{norm[1]}-{norm[2]}
                  </span>
                )}
              </div>
            ) : (
              <Field label="Messwert *">
                <input inputMode="decimal" value={value} required onChange={(e) => setValue(e.target.value)} />
              </Field>
            )}
            <Field label="Einheit">
              <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="z. B. °, cm, 0-5" />
            </Field>
          </>
        )}
        <TextField label="Notiz" value={notes} onChange={(v) => setNotes(v ?? "")} />
        <div className="wide">
          <ErrorBox error={error} />
          {lastAdded && !error && <p className="ok-text">✓ {lastAdded} gespeichert – nächsten Wert eingeben.</p>}
          <button className="btn primary" disabled={category === "test" && !result}>
            + Hinzufügen
          </button>
        </div>
      </form>

      <div className="chips">
        <button type="button" className={filter === "all" ? "chip on" : "chip"} onClick={() => setFilter("all")}>
          Alle
        </button>
        {(Object.keys(CATEGORY) as FindingCategory[]).map((c) => (
          <button key={c} type="button" className={filter === c ? "chip on" : "chip"} onClick={() => setFilter(c)}>
            {CATEGORY[c]}
          </button>
        ))}
      </div>

      {groups.length === 0 && <p className="muted card">Noch keine Befunde erfasst.</p>}
      {groups.map((g) => (
        <SeriesCard key={g[0].category + g[0].name + g[0].side} items={g} patientId={patientId} reload={reload} />
      ))}
    </div>
  );
}

function SeriesCard({ items, patientId, reload }: { items: Finding[]; patientId: number; reload: () => void }) {
  const first = items[0];
  const numeric = first.category !== "test";
  const [editing, setEditing] = useState<Finding | null>(null);
  const [voiding, setVoiding] = useState<Finding | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submitVoid(reason: string) {
    try {
      await api(`/patients/${patientId}/findings/${voiding!.id}/void`, { method: "POST", body: { reason } });
      setVoiding(null);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <article className="card">
      <header className="entry-head">
        <h3>
          {first.name}
          {first.side !== "none" && <span className="badge">{SIDE[first.side]}</span>}
          <span className="badge accent">{CATEGORY[first.category]}</span>
        </h3>
        {numeric && items.length >= 2 && (
          <span className="muted">
            {show(first)} → {show(items[items.length - 1])}
          </span>
        )}
      </header>
      {numeric && items.length >= 2 && (
        <LineChart
          title={first.name}
          unit={first.unit}
          series={[{ label: first.name, color: TEAL, points: items.map((i) => ({ date: i.recorded_on, value: i.value_num ?? 0 })) }]}
        />
      )}
      <div className="table-wrap">
        <table>
          <tbody>
            {[...items].reverse().map((f) => (
              <tr key={f.id}>
                <td>{formatDate(f.recorded_on)}</td>
                <td>
                  <strong className={f.value_text === "positiv" ? "danger-text" : undefined}>{show(f)}</strong>
                  {f.notes && <span className="muted"> – {f.notes}</span>}
                </td>
                <td className="row-actions">
                  {f.pending ? (
                    <span className="badge warn">offline erfasst</span>
                  ) : (
                    <>
                      <button className="btn small" onClick={() => setEditing(f)}>
                        Korrigieren
                      </button>
                      <button className="btn small danger" onClick={() => setVoiding(f)}>
                        Stornieren
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ErrorBox error={error} />
      {editing && (
        <Correction
          finding={editing}
          onClose={() => setEditing(null)}
          onSave={async (body) => {
            await api(`/patients/${patientId}/findings/${editing.id}`, { method: "PUT", body });
            setEditing(null);
            reload();
          }}
        />
      )}
      {voiding && <ReasonDialog title="Befund stornieren" confirmLabel="Stornieren" onConfirm={submitVoid} onCancel={() => setVoiding(null)} />}
    </article>
  );
}

function Correction({
  finding,
  onClose,
  onSave,
}: {
  finding: Finding;
  onClose: () => void;
  onSave: (body: FindingData & { correction_reason: string }) => Promise<void>;
}) {
  const [value, setValue] = useState(finding.category === "test" ? (finding.value_text ?? "") : String(finding.value_num ?? ""));
  const [opp, setOpp] = useState(String(finding.value_opposite ?? ""));
  const [neu, setNeu] = useState(String(finding.value_neutral ?? "0"));
  const pair = finding.value_opposite !== null;
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const isTest = finding.category === "test";

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await onSave({
        recorded_on: finding.recorded_on,
        category: finding.category,
        name: finding.name,
        side: finding.side,
        unit: finding.unit,
        notes: finding.notes,
        treatment_id: finding.treatment_id,
        value_num: isTest ? null : Number(value.replace(",", ".")),
        value_opposite: pair ? Number(opp.replace(",", ".")) : null,
        value_neutral: pair ? Number((neu || "0").replace(",", ".")) : null,
        value_text: isTest ? value : null,
        correction_reason: reason.trim(),
      });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="form-grid correction" onSubmit={submit}>
      {isTest ? (
        <Field label="Ergebnis">
          <select value={value} onChange={(e) => setValue(e.target.value)}>
            {["positiv", "negativ", "fraglich"].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </Field>
      ) : pair ? (
        <div className="field wide">
          <span className="field-label">Neue Werte (Gegenrichtung – Neutral – Hauptrichtung)</span>
          <div className="neutral-null">
            <input aria-label="Gegenrichtung" inputMode="decimal" value={opp} onChange={(e) => setOpp(e.target.value)} required />
            <span>–</span>
            <input aria-label="Neutral" inputMode="decimal" value={neu} onChange={(e) => setNeu(e.target.value)} required />
            <span>–</span>
            <input aria-label="Hauptrichtung" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} required />
          </div>
        </div>
      ) : (
        <Field label={`Neuer Wert${finding.unit ? " (" + finding.unit + ")" : ""}`}>
          <input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} required />
        </Field>
      )}
      <TextField label="Grund der Korrektur" value={reason} onChange={(v) => setReason(v ?? "")} required />
      <div className="wide">
        <ErrorBox error={error} />
        <div className="actions">
          <button type="button" className="btn" onClick={onClose}>
            Abbrechen
          </button>
          <button className="btn primary" disabled={!reason.trim()}>
            Korrektur speichern
          </button>
        </div>
      </div>
    </form>
  );
}
