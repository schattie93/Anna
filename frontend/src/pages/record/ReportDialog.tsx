import { useState, type FormEvent } from "react";
import { api, openPdf } from "../../api";
import { useAssistStatus } from "../../hooks";
import { ErrorBox, TextArea, TextField } from "../../components/fields";
import Modal from "../../components/Modal";

export default function ReportDialog({ patientId, defaultRecipient, onClose }: { patientId: number; defaultRecipient: string | null; onClose: () => void }) {
  const [recipient, setRecipient] = useState(defaultRecipient ?? "");
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const assist = useAssistStatus();
  const [drafting, setDrafting] = useState(false);
  const [draftNotice, setDraftNotice] = useState<string | null>(null);

  async function draft() {
    setDrafting(true);
    setError(null);
    try {
      const res = await api<{ text: string; notice: string }>(`/patients/${patientId}/assist/report-draft`, { method: "POST" });
      setSummary(res.text);
      setDraftNotice(res.notice);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDrafting(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await openPdf(`/patients/${patientId}/report.pdf`, {
        recipient: recipient.trim() || null,
        from_date: from,
        to_date: to,
        summary: summary?.trim() || null,
      });
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Therapiebericht (PDF)" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <TextField label="Empfänger" value={recipient} onChange={(v) => setRecipient(v ?? "")} wide hint="z. B. verordnende Ärztin / verordnender Arzt" />
        <TextField label="Behandlungen ab" type="date" value={from} onChange={setFrom} />
        <TextField label="bis" type="date" value={to} onChange={setTo} />
        <TextArea label="Beurteilung und weiteres Vorgehen" value={summary} onChange={setSummary} rows={6} placeholder="Zusammenfassung des Verlaufs, Empfehlung zur Weiterbehandlung …" />
        {assist.suggest && (
          <div className="wide">
            <button type="button" className="btn" onClick={draft} disabled={drafting}>
              {drafting ? "Entwurf wird erstellt …" : "✨ Entwurf aus dem Verlauf erstellen (lokale KI)"}
            </button>
            {draftNotice && <p className="ai-notice">{draftNotice}</p>}
          </div>
        )}
        <p className="muted wide">Der Bericht enthält Diagnosen, Verlauf, Schmerzdiagramm, Befundentwicklung und Therapieziele.</p>
        <ErrorBox error={error} />
        <div className="actions wide">
          <button type="button" className="btn" onClick={onClose}>
            Abbrechen
          </button>
          <button className="btn primary" disabled={busy}>
            PDF erstellen
          </button>
        </div>
      </form>
    </Modal>
  );
}
