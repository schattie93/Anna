import { useState } from "react";
import { api, type SoapSuggestion } from "../api";
import { useAssistStatus } from "../hooks";
import { ErrorBox, TextArea } from "./fields";
import Modal from "./Modal";

type Fields = { subjective: string | null; objective: string | null; assessment: string | null; plan: string | null };

const LABELS: Record<keyof Fields, string> = {
  subjective: "S – Subjektiv",
  objective: "O – Objektiv",
  assessment: "A – Beurteilung",
  plan: "P – Plan",
};

/** Strukturiert ein Diktat oder Stichpunkte per lokalem Sprachmodell in SOAP-Felder. Übernommen wird erst nach Prüfung. */
export default function SoapAssist({ current, onApply }: { current: Fields; onApply: (fields: Fields) => void }) {
  const assist = useAssistStatus();
  const [raw, setRaw] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<SoapSuggestion | null>(null);

  if (!assist.suggest) return null;

  async function run() {
    if (!raw?.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setProposal(await api<SoapSuggestion>("/assist/soap", { method: "POST", body: { task: "soap", text: raw } }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function apply() {
    if (!proposal) return;
    const merged = { ...current };
    for (const k of Object.keys(LABELS) as (keyof Fields)[]) {
      const add = proposal[k]?.trim();
      if (add) merged[k] = current[k]?.trim() ? `${current[k]!.trim()}\n${add}` : add;
    }
    onApply(merged);
    setProposal(null);
    setRaw(null);
  }

  return (
    <details className="card soap-assist">
      <summary>✨ Aus Diktat oder Stichpunkten strukturieren (lokale KI)</summary>
      <div className="stack">
        <TextArea label="Rohnotiz / Diktat" value={raw} onChange={setRaw} rows={4} placeholder="Frei diktieren oder tippen – die Zuordnung zu S, O, A, P übernimmt das Sprachmodell." />
        <ErrorBox error={error} />
        <div className="actions">
          <button type="button" className="btn primary" onClick={run} disabled={busy || !raw?.trim()}>
            {busy ? "Wird erstellt …" : "Vorschlag erstellen"}
          </button>
        </div>
      </div>
      {proposal && (
        <Modal title="KI-Vorschlag prüfen" onClose={() => setProposal(null)} wide>
          <p className="ai-notice">{proposal.notice}</p>
          <div className="form-grid">
            {(Object.keys(LABELS) as (keyof Fields)[]).map((k) => (
              <TextArea key={k} label={LABELS[k]} value={proposal[k]} onChange={(v) => setProposal({ ...proposal, [k]: v })} rows={3} />
            ))}
          </div>
          <div className="actions">
            <button type="button" className="btn" onClick={() => setProposal(null)}>
              Verwerfen
            </button>
            <button type="button" className="btn primary" onClick={apply}>
              Geprüft – in die Behandlung übernehmen
            </button>
          </div>
        </Modal>
      )}
    </details>
  );
}
