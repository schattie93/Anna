import { useState } from "react";
import { apiUpload } from "../api";
import DrawingCanvas from "./DrawingCanvas";
import Modal from "./Modal";

/**
 * Stift-Taste für Textfelder: Mit dem Stift schreiben, die Handschrift wird lokal erkannt und nach Prüfung ins Feld übernommen.
 * (Eigene Textarea statt fields.tsx, um zirkuläre Importe zu vermeiden.)
 */
export default function HandwritingButton({ onText }: { onText: (text: string) => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);

  function close() {
    setOpen(false);
    setText(null);
    setError(null);
  }

  async function recognize(png: Blob) {
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.set("file", new File([png], "handschrift.png", { type: "image/png" }));
      const res = await apiUpload<{ text: string }>("/assist/handwriting", form);
      setText(res.text);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className="mic" onClick={() => setOpen(true)} aria-label="Mit Stift schreiben" title="Mit Stift schreiben (Handschrift wird lokal erkannt)">
        ✍
      </button>
      {open && (
        <Modal title="Mit Stift schreiben" onClose={close} wide>
          {text === null ? (
            <div className="stack">
              <p className="muted">Schreiben Sie in die Fläche und tippen Sie auf „Text erkennen“. Das Ergebnis können Sie vor dem Übernehmen korrigieren.</p>
              {error && <p className="error">{error}</p>}
              <DrawingCanvas size={{ w: 1400, h: 500 }} label={busy ? "Erkenne …" : "Text erkennen"} saving={busy} onCancel={close} onSave={recognize} />
            </div>
          ) : (
            <div className="stack">
              <p className="ai-notice">KI-Transkription – bitte vollständig prüfen, bevor sie übernommen wird.</p>
              <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} aria-label="Erkannter Text" />
              <div className="actions">
                <button type="button" className="btn" onClick={() => setText(null)}>
                  Nochmal schreiben
                </button>
                <button
                  type="button"
                  className="btn primary"
                  disabled={!text.trim()}
                  onClick={() => {
                    onText(text.trim());
                    close();
                  }}
                >
                  Geprüft – übernehmen
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
