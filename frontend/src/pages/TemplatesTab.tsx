import { useState, type FormEvent } from "react";
import { api, type CatalogItem } from "../api";
import { ErrorBox, Field, TextField } from "../components/fields";
import Modal from "../components/Modal";
import { useApi } from "../hooks";
import { CATEGORY } from "../labels";

const KINDS: { kind: CatalogItem["kind"]; title: string; help: string }[] = [
  { kind: "red_flag", title: "Warnzeichen (Red Flags)", help: "Erscheinen in der Anamnese zum Antippen. Positive Warnzeichen werden oben in der Akte angezeigt." },
  { kind: "yellow_flag", title: "Psychosoziale Faktoren (Yellow Flags)", help: "Hinweise auf ein Chronifizierungsrisiko, in der Anamnese zum Antippen." },
  { kind: "measure", title: "Maßnahmen", help: "Schnellauswahl in der Behandlungsdokumentation und Grundlage der Auswertung." },
  { kind: "finding_preset", title: "Befundvorlagen (Messwerte, Tests, Assessments)", help: "Vorschläge im Reiter „Messwerte & Tests“. Bei Beweglichkeit nach Neutral-Null-Methode: Name im Format „Gelenk (Gegenrichtung/Hauptrichtung)“, Richtwerte optional." },
];

export default function TemplatesTab() {
  const ops = useApi<{ unreviewed_templates: number }>("/admin/ops");
  return (
    <div className="stack">
      <section className="card">
        <h2>Vorlagen der Praxis</h2>
        <p className="muted">
          Hier passen Sie die fachlichen Vorlagen an. Die mitgelieferten Standardwerte sind <strong>nicht fachlich geprüft</strong> und bis zur Freigabe als „ungeprüft“ markiert. Vorlagen werden nie gelöscht, sondern deaktiviert, weil ältere
          Akten auf sie verweisen. Änderungen wirken sofort für alle und werden protokolliert.
        </p>
        {ops.data && ops.data.unreviewed_templates > 0 && <p className="ai-notice">{ops.data.unreviewed_templates} Vorlagen sind noch nicht als geprüft markiert.</p>}
      </section>
      {KINDS.map((k) => (
        <KindSection key={k.kind} {...k} onReviewed={ops.reload} />
      ))}
    </div>
  );
}

function KindSection({ kind, title, help, onReviewed }: { kind: CatalogItem["kind"]; title: string; help: string; onReviewed: () => void }) {
  const { data, error, reload } = useApi<CatalogItem[]>(`/admin/catalog?kind=${kind}`);
  const [editing, setEditing] = useState<CatalogItem | "new" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const unreviewed = (data ?? []).filter((i) => i.active && !i.reviewed).length;
  const refresh = () => {
    reload();
    onReviewed();
  };

  async function move(i: CatalogItem, direction: "up" | "down") {
    setErr(null);
    try {
      await api(`/admin/catalog/${i.id}/move`, { method: "POST", body: { direction } });
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function reviewAll() {
    await api("/admin/catalog/review-all", { method: "POST", body: { kind } });
    refresh();
  }

  return (
    <section className="card stack">
      <div className="page-head">
        <h3>{title}</h3>
        <div className="actions">
          {unreviewed > 0 && (
            <button className="btn small" onClick={reviewAll} title="Bestätigt, dass Sie diese Liste durchgesehen haben">
              Alle {unreviewed} als geprüft markieren
            </button>
          )}
          <button className="btn small primary" onClick={() => setEditing("new")}>
            + Neu
          </button>
        </div>
      </div>
      <p className="muted">{help}</p>
      <ErrorBox error={error ?? err} />
      <div className="table-wrap">
        <table>
          <tbody>
            {(data ?? []).map((i, idx) => (
              <tr key={i.id} className={i.active ? undefined : "struck"}>
                <td className="reorder">
                  <button className="btn small" aria-label="nach oben" disabled={idx === 0} onClick={() => move(i, "up")}>
                    ↑
                  </button>
                  <button className="btn small" aria-label="nach unten" disabled={idx === (data?.length ?? 0) - 1} onClick={() => move(i, "down")}>
                    ↓
                  </button>
                </td>
                <td>
                  {i.label}
                  {kind === "finding_preset" && (
                    <span className="muted block">
                      {i.category ? CATEGORY[i.category] : ""}
                      {i.unit ? ` · ${i.unit}` : ""}
                      {i.norm_main !== null ? ` · Richtwert ${i.norm_opposite}-${i.norm_neutral}-${i.norm_main}` : ""}
                    </span>
                  )}
                </td>
                <td>
                  {!i.active ? <span className="badge">inaktiv</span> : i.reviewed ? <span className="badge ok" title={i.reviewed_by ?? ""}>geprüft</span> : <span className="badge warn">ungeprüft</span>}
                </td>
                <td className="row-actions">
                  <button className="btn small" onClick={() => setEditing(i)}>
                    Bearbeiten
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && (
        <ItemDialog
          kind={kind}
          item={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
    </section>
  );
}

function ItemDialog({ kind, item, onClose, onSaved }: { kind: CatalogItem["kind"]; item: CatalogItem | null; onClose: () => void; onSaved: () => void }) {
  const [label, setLabel] = useState(item?.label ?? "");
  const [category, setCategory] = useState<string>(item?.category ?? "rom");
  const [unit, setUnit] = useState(item?.unit ?? "");
  const [n1, setN1] = useState(item?.norm_opposite?.toString() ?? "");
  const [n2, setN2] = useState(item?.norm_neutral?.toString() ?? "");
  const [n3, setN3] = useState(item?.norm_main?.toString() ?? "");
  const [active, setActive] = useState(item?.active ?? true);
  const [reviewed, setReviewed] = useState(item?.reviewed ?? true);
  const [error, setError] = useState<string | null>(null);
  const num = (v: string) => (v.trim() === "" ? null : Number(v.replace(",", ".")));
  const isPreset = kind === "finding_preset";

  async function submit(e: FormEvent) {
    e.preventDefault();
    const norms = { norm_opposite: num(n1), norm_neutral: num(n2), norm_main: num(n3) };
    if (isPreset && Object.values(norms).some((v) => v !== null && Number.isNaN(v))) return setError("Richtwerte müssen Zahlen sein");
    try {
      const common = { label, category: isPreset ? category : null, unit: isPreset ? unit || null : null, ...(isPreset && category === "rom" ? norms : { norm_opposite: null, norm_neutral: null, norm_main: null }) };
      if (item) await api(`/admin/catalog/${item.id}`, { method: "PUT", body: { ...common, active, reviewed } });
      else await api("/admin/catalog", { method: "POST", body: { kind, ...common } });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Modal title={item ? "Vorlage bearbeiten" : "Neue Vorlage"} onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <TextField label="Text" value={label} onChange={(v) => setLabel(v ?? "")} required wide autoFocus />
        {isPreset && (
          <>
            <Field label="Kategorie">
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                {Object.entries(CATEGORY).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
            <TextField label="Einheit" value={unit} onChange={(v) => setUnit(v ?? "")} placeholder="z. B. °, cm, 0-5" />
            {category === "rom" && (
              <div className="field wide">
                <span className="field-label">Richtwerte Neutral-Null (Gegenrichtung – Neutral – Hauptrichtung, optional)</span>
                <div className="neutral-null">
                  <input aria-label="Richtwert Gegenrichtung" inputMode="decimal" value={n1} onChange={(e) => setN1(e.target.value)} />
                  <span>–</span>
                  <input aria-label="Richtwert Neutral" inputMode="decimal" value={n2} onChange={(e) => setN2(e.target.value)} />
                  <span>–</span>
                  <input aria-label="Richtwert Hauptrichtung" inputMode="decimal" value={n3} onChange={(e) => setN3(e.target.value)} />
                </div>
              </div>
            )}
          </>
        )}
        {item && (
          <div className="wide checks">
            <label className="check">
              <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
              <span>Aktiv (wird zur Auswahl angeboten)</span>
            </label>
            <label className="check">
              <input type="checkbox" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />
              <span>Von der Praxis fachlich geprüft</span>
            </label>
          </div>
        )}
        <div className="wide">
          <ErrorBox error={error} />
        </div>
        <div className="actions wide">
          <button type="button" className="btn" onClick={onClose}>
            Abbrechen
          </button>
          <button className="btn primary">Speichern</button>
        </div>
      </form>
    </Modal>
  );
}
