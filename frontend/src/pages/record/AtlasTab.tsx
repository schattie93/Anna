import { useMemo, useState } from "react";
import { api, type BodyMark, type BodyMarkData, type MarkKind } from "../../api";
import BodyAtlas, { KIND_COLOR } from "../../components/BodyAtlas";
import { ErrorBox, PainScale, ReasonDialog, TextField } from "../../components/fields";
import { MARK_KIND, formatDate, today } from "../../labels";
import { TabHead } from "./common";

export default function AtlasTab({ patientId, entries, reload }: { patientId: number; entries: BodyMark[]; reload: () => void }) {
  const [kind, setKind] = useState<MarkKind>("pain");
  const [intensity, setIntensity] = useState<number | null>(5);
  const [date, setDate] = useState(today());
  const [shownDate, setShownDate] = useState<string>("all");
  const [selected, setSelected] = useState<BodyMark | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [voiding, setVoiding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const active = entries.filter((m) => !m.voided);
  const dates = useMemo(() => [...new Set(active.map((m) => m.recorded_on))].sort().reverse(), [active]);
  const visible = shownDate === "all" ? active : active.filter((m) => m.recorded_on === shownDate);

  async function place(view: "front" | "back", x: number, y: number) {
    setError(null);
    const body: BodyMarkData = { recorded_on: date, view, x, y, kind, intensity: kind === "pain" || kind === "tension" ? intensity : null, note: null, treatment_id: null };
    try {
      await api(`/patients/${patientId}/body-marks`, { method: "POST", body });
      setShownDate((d) => (d === "all" || d === date ? d : date));
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function select(m: BodyMark) {
    setSelected(m);
    setNoteDraft(m.note ?? "");
  }

  async function saveSelected(patch: Partial<BodyMarkData>) {
    if (!selected) return;
    const data: BodyMarkData = {
      recorded_on: selected.recorded_on,
      view: selected.view,
      x: selected.x,
      y: selected.y,
      kind: selected.kind,
      intensity: selected.intensity,
      note: selected.note,
      treatment_id: selected.treatment_id,
    };
    try {
      const updated = await api<BodyMark>(`/patients/${patientId}/body-marks/${selected.id}`, { method: "PUT", body: { ...data, ...patch } });
      setSelected(updated);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function doVoid(reason: string) {
    try {
      await api(`/patients/${patientId}/body-marks/${selected!.id}/void`, { method: "POST", body: { reason } });
      setSelected(null);
      setVoiding(false);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="stack">
      <TabHead title="Körperatlas" newLabel="" />
      <section className="card form-grid">
        <div className="field wide">
          <span className="field-label">1. Art der Markierung wählen, 2. auf den Körper tippen</span>
          <div className="chips">
            {(Object.keys(MARK_KIND) as MarkKind[]).map((k) => (
              <button key={k} type="button" aria-pressed={kind === k} className={kind === k ? "chip on" : "chip"} onClick={() => setKind(k)}>
                <i className="dot" style={{ background: KIND_COLOR[k] }} /> {MARK_KIND[k]}
              </button>
            ))}
          </div>
        </div>
        {(kind === "pain" || kind === "tension") && <PainScale label="Intensität (NRS 0–10)" value={intensity} onChange={setIntensity} />}
        <TextField label="Datum der Markierung" type="date" value={date} onChange={(v) => setDate(v ?? "")} required />
        <div className="field">
          <span className="field-label">Anzeige</span>
          <select value={shownDate} onChange={(e) => setShownDate(e.target.value)}>
            <option value="all">Alle Termine überlagert</option>
            {dates.map((d) => (
              <option key={d} value={d}>
                nur {formatDate(d)}
              </option>
            ))}
          </select>
        </div>
      </section>
      <ErrorBox error={error} />

      <div className="atlas-pair card">
        {(["front", "back"] as const).map((view) => (
          <figure key={view}>
            <BodyAtlas view={view} marks={visible} onPlace={(x, y) => place(view, x, y)} selectedId={selected?.id} onSelect={select} />
            <figcaption>{view === "front" ? "Vorderansicht" : "Rückansicht"}</figcaption>
          </figure>
        ))}
      </div>

      {selected && (
        <section className="card form-grid">
          <h3 className="wide">
            Markierung vom {formatDate(selected.recorded_on)} · {MARK_KIND[selected.kind]}
          </h3>
          <PainScale label="Intensität" value={selected.intensity} onChange={(v) => saveSelected({ intensity: v })} />
          <TextField label="Notiz" value={noteDraft} onChange={(v) => setNoteDraft(v ?? "")} />
          <div className="actions wide">
            <button className="btn danger" onClick={() => setVoiding(true)}>
              Stornieren
            </button>
            <button className="btn" onClick={() => saveSelected({ note: noteDraft.trim() || null })}>
              Notiz speichern
            </button>
            <button className="btn primary" onClick={() => setSelected(null)}>
              Fertig
            </button>
          </div>
        </section>
      )}

      {visible.length > 0 && (
        <section className="card">
          <h3>Markierungen ({visible.length})</h3>
          <ul className="plain">
            {visible.map((m) => (
              <li key={m.id}>
                <button className="link-btn" onClick={() => select(m)}>
                  {formatDate(m.recorded_on)} · {m.view === "front" ? "vorne" : "hinten"} · {MARK_KIND[m.kind]}
                  {m.intensity !== null ? ` ${m.intensity}/10` : ""}
                  {m.note ? ` – ${m.note}` : ""}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {voiding && <ReasonDialog title="Markierung stornieren" confirmLabel="Stornieren" onConfirm={doVoid} onCancel={() => setVoiding(false)} />}
    </div>
  );
}
