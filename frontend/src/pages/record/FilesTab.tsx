import { useRef, useState, type FormEvent } from "react";
import { api, apiUpload, type Attachment, type AttachmentKind } from "../../api";
import DrawingCanvas from "../../components/DrawingCanvas";
import { ErrorBox, ReasonDialog, TextField } from "../../components/fields";
import Modal from "../../components/Modal";
import { formatDate, today } from "../../labels";

const KIND_LABEL: Record<AttachmentKind, string> = { photo: "Foto", document: "Dokument", drawing: "Zeichnung" };

const fileUrl = (patientId: number, a: Attachment, thumb = false) => `/api/patients/${patientId}/attachments/${a.id}/${thumb ? "thumb" : "file"}`;

export default function FilesTab({ patientId, entries, reload }: { patientId: number; entries: Attachment[]; reload: () => void }) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [date, setDate] = useState(today());
  const [drawing, setDrawing] = useState<{ background?: string; parent?: Attachment } | null>(null);
  const [open, setOpen] = useState<Attachment | null>(null);
  const [compare, setCompare] = useState<number[]>([]);
  const [comparing, setComparing] = useState(false);
  const [voiding, setVoiding] = useState<Attachment | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<AttachmentKind | "all">("all");

  const items = entries.filter((a) => !a.voided && (filter === "all" || a.kind === filter));

  function choose(file: File | undefined) {
    if (!file) return;
    setPending(file);
    setCaption("");
    setDate(today());
  }

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!pending) return;
    setSaving(true);
    setError(null);
    const form = new FormData();
    form.set("file", pending);
    form.set("kind", pending.type === "application/pdf" ? "document" : "photo");
    form.set("taken_on", date);
    if (caption.trim()) form.set("caption", caption.trim());
    try {
      await apiUpload(`/patients/${patientId}/attachments`, form);
      setPending(null);
      reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function saveDrawing(png: Blob) {
    setSaving(true);
    setError(null);
    const form = new FormData();
    form.set("file", new File([png], "zeichnung.png", { type: "image/png" }));
    form.set("kind", "drawing");
    form.set("taken_on", today());
    form.set("caption", drawing?.parent ? `Einzeichnung: ${drawing.parent.caption ?? drawing.parent.filename}` : "Zeichnung / Notiz");
    if (drawing?.parent) form.set("parent_id", String(drawing.parent.id));
    try {
      await apiUpload(`/patients/${patientId}/attachments`, form);
      setDrawing(null);
      setOpen(null);
      reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function doVoid(reason: string) {
    try {
      await api(`/patients/${patientId}/attachments/${voiding!.id}/void`, { method: "POST", body: { reason } });
      setVoiding(null);
      setOpen(null);
      reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (drawing) {
    return (
      <div className="stack">
        <h2>{drawing.parent ? "In Bild einzeichnen" : "Zeichnung / handschriftliche Notiz"}</h2>
        <ErrorBox error={error} />
        <DrawingCanvas background={drawing.background} onSave={saveDrawing} onCancel={() => setDrawing(null)} saving={saving} />
      </div>
    );
  }

  const toCompare = compare.map((id) => entries.find((a) => a.id === id)).filter((a): a is Attachment => !!a);

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Bilder &amp; Dokumente</h2>
        <div className="actions">
          <button className="btn" onClick={() => cameraRef.current?.click()}>
            📷 Foto aufnehmen
          </button>
          <button className="btn" onClick={() => fileRef.current?.click()}>
            Datei wählen
          </button>
          <button className="btn primary" onClick={() => setDrawing({})}>
            ✎ Zeichnen
          </button>
        </div>
      </div>
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,application/pdf" hidden onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />

      {pending && (
        <form className="card form-grid" onSubmit={upload}>
          <h3 className="wide">{pending.name}</h3>
          <TextField label="Beschriftung" value={caption} onChange={(v) => setCaption(v ?? "")} placeholder="z. B. Haltung von hinten, vor Behandlung" autoFocus />
          <TextField label="Aufnahmedatum" type="date" value={date} onChange={(v) => setDate(v ?? "")} required />
          <div className="actions wide">
            <button type="button" className="btn" onClick={() => setPending(null)}>
              Abbrechen
            </button>
            <button className="btn primary" disabled={saving}>
              Hochladen
            </button>
          </div>
        </form>
      )}
      <ErrorBox error={error} />

      <div className="chips">
        {(["all", "photo", "document", "drawing"] as const).map((k) => (
          <button key={k} type="button" className={filter === k ? "chip on" : "chip"} onClick={() => setFilter(k)}>
            {k === "all" ? "Alle" : KIND_LABEL[k]}
          </button>
        ))}
        {compare.length === 2 && (
          <button className="btn small primary" onClick={() => setComparing(true)}>
            Vorher/Nachher vergleichen
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="muted card">Noch keine Dateien.</p>
      ) : (
        <div className="gallery">
          {items.map((a) => (
            <figure key={a.id} className="tile">
              <button type="button" className="tile-img" onClick={() => setOpen(a)} aria-label={`${KIND_LABEL[a.kind]} öffnen`}>
                {a.has_thumb ? <img src={fileUrl(patientId, a, true)} alt={a.caption ?? a.filename} loading="lazy" /> : <span className="pdf-icon">PDF</span>}
              </button>
              <figcaption>
                <strong>{a.caption ?? a.filename}</strong>
                <span className="muted">
                  {KIND_LABEL[a.kind]} · {formatDate(a.taken_on)}
                </span>
                {a.has_thumb && (
                  <label className="check small-check">
                    <input
                      type="checkbox"
                      checked={compare.includes(a.id)}
                      onChange={(e) => setCompare((c) => (e.target.checked ? [...c, a.id].slice(-2) : c.filter((x) => x !== a.id)))}
                    />
                    <span>zum Vergleich</span>
                  </label>
                )}
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      {open && (
        <Modal title={open.caption ?? open.filename} onClose={() => setOpen(null)} wide>
          <p className="muted">
            {KIND_LABEL[open.kind]} · {formatDate(open.taken_on)} · {open.created_by.full_name}
          </p>
          {open.content_type === "application/pdf" ? (
            <p>
              <a className="btn primary" href={fileUrl(patientId, open)} target="_blank" rel="noreferrer">
                PDF öffnen
              </a>
            </p>
          ) : (
            <img className="viewer" src={fileUrl(patientId, open)} alt={open.caption ?? open.filename} />
          )}
          <div className="actions">
            {open.content_type !== "application/pdf" && (
              <button className="btn" onClick={() => {
                  setDrawing({ background: fileUrl(patientId, open), parent: open });
                  setOpen(null);
                }}>
                ✎ Einzeichnen
              </button>
            )}
            <button className="btn danger" onClick={() => setVoiding(open)}>
              Stornieren
            </button>
          </div>
        </Modal>
      )}

      {comparing && toCompare.length === 2 && (
        <Modal title="Vorher/Nachher" onClose={() => setComparing(false)} wide>
          <div className="compare">
            {[...toCompare].sort((a, b) => a.taken_on.localeCompare(b.taken_on)).map((a) => (
              <figure key={a.id}>
                <img src={fileUrl(patientId, a)} alt={a.caption ?? a.filename} />
                <figcaption>
                  {formatDate(a.taken_on)} – {a.caption ?? a.filename}
                </figcaption>
              </figure>
            ))}
          </div>
        </Modal>
      )}
      {voiding && <ReasonDialog title="Datei stornieren" confirmLabel="Stornieren" onConfirm={doVoid} onCancel={() => setVoiding(null)} />}
    </div>
  );
}
