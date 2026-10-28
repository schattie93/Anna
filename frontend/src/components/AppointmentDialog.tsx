import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Appointment, type AppointmentCreated, type PatientListItem, type Prescription, type Treatment } from "../api";
import { useUser } from "../auth";
import { APPT_STATUS, formatDate, formatTime, isoDate } from "../labels";
import { ErrorBox, Field, TextField } from "./fields";
import Modal from "./Modal";
import PatientPicker from "./PatientPicker";

const DURATIONS = [15, 20, 25, 30, 45, 60, 90];

function toLocalInput(d: Date): string {
  return `${isoDate(d)}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** Neuer Termin (auch Serie oder Blockzeit). */
export function NewAppointmentDialog({ start, patient: initialPatient, onClose, onSaved }: { start: Date; patient?: PatientListItem | null; onClose: () => void; onSaved: () => void }) {
  const medical = useUser().role !== "reception";
  const me = useUser();
  const [patient, setPatient] = useState<PatientListItem | null>(initialPatient ?? null);
  const [block, setBlock] = useState(false);
  const [title, setTitle] = useState("");
  const [when, setWhen] = useState(toLocalInput(start));
  const [duration, setDuration] = useState(30);
  const [repeat, setRepeat] = useState(1);
  const [every, setEvery] = useState(7);
  const [note, setNote] = useState("");
  const [rxId, setRxId] = useState<number | null>(null);
  const [rxs, setRxs] = useState<Prescription[]>([]);
  const [therapists, setTherapists] = useState<{ id: number; full_name: string }[]>([]);
  const [therapistId, setTherapistId] = useState<number | null>(me.role === "reception" ? null : me.id);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [skipped, setSkipped] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!patient || !medical) {
      setRxs([]);
      setRxId(null);
      return;
    }
    api<Prescription[]>(`/patients/${patient.id}/prescriptions`).then((list) => {
      const open = list.filter((r) => !r.voided && r.status === "open");
      setRxs(open);
      setRxId(open[0]?.id ?? null);
    }, () => setRxs([]));
  }, [patient, medical]);

  useEffect(() => {
    api<{ id: number; full_name: string; role: string; is_active: boolean }[]>("/users/therapists").then((u) => {
      setTherapists(u);
      setTherapistId((cur) => cur ?? u[0]?.id ?? null);
    }, () => undefined);
  }, []);

  async function save(e?: FormEvent, force = false) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    setConflict(false);
    try {
      const res = await api<AppointmentCreated>("/appointments", {
        method: "POST",
        body: {
          patient_id: block ? null : patient?.id ?? null,
          therapist_id: therapistId,
          prescription_id: block ? null : rxId,
          start: new Date(when).toISOString(),
          duration_minutes: duration,
          title: block ? title : null,
          note: note.trim() || null,
          repeat_count: repeat,
          repeat_days: every,
          force,
        },
      });
      if (res.skipped.length > 0) {
        setSkipped(res.skipped.map((s) => `${formatDate(s.start)} ${formatTime(s.start)}: ${s.reason}`));
        onSaved();
      } else {
        onSaved();
        onClose();
      }
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      setConflict(msg.startsWith("Überschneidung"));
    } finally {
      setBusy(false);
    }
  }

  if (skipped.length > 0) {
    return (
      <Modal title="Serie angelegt" onClose={onClose}>
        <p>Einige Termine wurden übersprungen:</p>
        <ul className="plain">
          {skipped.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        <div className="actions">
          <button className="btn primary" onClick={onClose}>
            OK
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Neuer Termin" onClose={onClose}>
      <form className="form-grid" onSubmit={save}>
        <label className="check wide">
          <input type="checkbox" checked={block} onChange={(e) => setBlock(e.target.checked)} />
          <span>Blockzeit (Pause, Fortbildung, Hausbesuche …) statt Patiententermin</span>
        </label>
        {block ? (
          <TextField label="Bezeichnung" value={title} onChange={(v) => setTitle(v ?? "")} required wide autoFocus />
        ) : (
          <div className="field wide">
            <span className="field-label">Patient *</span>
            <PatientPicker value={patient} onChange={setPatient} autoFocus={!initialPatient} />
          </div>
        )}
        <TextField label="Beginn" type="datetime-local" value={when} onChange={(v) => setWhen(v ?? "")} required />
        <Field label="Dauer">
          <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            {DURATIONS.map((d) => (
              <option key={d} value={d}>
                {d} Minuten
              </option>
            ))}
          </select>
        </Field>
        {me.role === "reception" && (
          <Field label="Behandler/in">
            <select value={therapistId ?? ""} onChange={(e) => setTherapistId(Number(e.target.value))} required>
              {therapists.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {!block && rxs.length > 0 && (
          <Field label="Verordnung">
            <select value={rxId ?? ""} onChange={(e) => setRxId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">– keine –</option>
              {rxs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.measure} ({r.units_done}/{r.total_units}) vom {formatDate(r.issued_on)}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Wiederholen (Anzahl Termine)">
          <input type="number" min={1} max={52} value={repeat} onChange={(e) => setRepeat(Math.max(1, Number(e.target.value)))} />
        </Field>
        {repeat > 1 && (
          <Field label="Abstand">
            <select value={every} onChange={(e) => setEvery(Number(e.target.value))}>
              <option value={7}>wöchentlich</option>
              <option value={14}>alle 2 Wochen</option>
              <option value={3}>alle 3 Tage</option>
              <option value={1}>täglich</option>
            </select>
          </Field>
        )}
        <TextField label="Notiz" value={note} onChange={(v) => setNote(v ?? "")} wide />
        <div className="wide">
          <ErrorBox error={error} />
        </div>
        <div className="actions wide">
          <button type="button" className="btn" onClick={onClose}>
            Abbrechen
          </button>
          {conflict && (
            <button type="button" className="btn" onClick={() => save(undefined, true)}>
              Trotzdem anlegen
            </button>
          )}
          <button className="btn primary" disabled={busy || (!block && !patient)}>
            Termin anlegen
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** Termin ansehen: Status ändern, verschieben, Behandlung starten. */
export function AppointmentDialog({ appointment: a, onClose, onChanged }: { appointment: Appointment; onClose: () => void; onChanged: () => void }) {
  const medical = useUser().role !== "reception";
  const navigate = useNavigate();
  const [moving, setMoving] = useState(false);
  const [when, setWhen] = useState(toLocalInput(new Date(a.start)));
  const [reason, setReason] = useState("");
  const [cancelling, setCancelling] = useState<"cancelled" | "no_show" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  async function patch(body: object, force = false) {
    setError(null);
    setConflict(false);
    try {
      await api(`/appointments/${a.id}`, { method: "PATCH", body: { ...body, force } });
      onChanged();
      onClose();
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      setConflict(msg.startsWith("Überschneidung"));
    }
  }

  async function startTreatment() {
    setError(null);
    try {
      const t = await api<Treatment>(`/appointments/${a.id}/start`, { method: "POST", body: { treated_on: isoDate(new Date(a.start)) } });
      onChanged();
      navigate(`/patienten/${t.patient_id}/behandlungen`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const label = a.patient ? `${a.patient.last_name}, ${a.patient.first_name}` : (a.title ?? "Blockzeit");
  const open = a.status === "planned";

  return (
    <Modal title={label} onClose={onClose}>
      <p className="muted">
        {formatDate(a.start)} · {formatTime(a.start)}–{formatTime(a.end)} · {a.therapist.full_name} · <strong>{APPT_STATUS[a.status]}</strong>
        {a.prescription_label && <> · {a.prescription_label}</>}
      </p>
      {a.note && <p>{a.note}</p>}
      {a.cancel_reason && <p className="muted">Grund: {a.cancel_reason}</p>}
      <ErrorBox error={error} />

      {moving && (
        <form
          className="form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            patch({ start: new Date(when).toISOString() });
          }}
        >
          <TextField label="Neuer Beginn" type="datetime-local" value={when} onChange={(v) => setWhen(v ?? "")} required />
          <div className="actions wide">
            {conflict && (
              <button type="button" className="btn" onClick={() => patch({ start: new Date(when).toISOString() }, true)}>
                Trotzdem verschieben
              </button>
            )}
            <button className="btn primary">Verschieben</button>
          </div>
        </form>
      )}

      {cancelling && (
        <form
          className="form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            patch({ status: cancelling, cancel_reason: reason.trim() || null });
          }}
        >
          <TextField label={cancelling === "cancelled" ? "Grund der Absage" : "Anmerkung"} value={reason} onChange={(v) => setReason(v ?? "")} autoFocus wide />
          <div className="actions wide">
            <button type="button" className="btn" onClick={() => setCancelling(null)}>
              Zurück
            </button>
            <button className="btn primary">{cancelling === "cancelled" ? "Absagen" : "Als nicht erschienen markieren"}</button>
          </div>
        </form>
      )}

      {!moving && !cancelling && (
        <div className="actions">
          {a.patient && (
            <Link to={`/patienten/${a.patient.id}`} className="btn" onClick={onClose}>
              Zur Akte
            </Link>
          )}
          {open && (
            <>
              <button className="btn" onClick={() => setMoving(true)}>
                Verschieben
              </button>
              <button className="btn danger" onClick={() => setCancelling("cancelled")}>
                Absagen
              </button>
              {a.patient && (
                <button className="btn danger" onClick={() => setCancelling("no_show")}>
                  Nicht erschienen
                </button>
              )}
              {!a.patient && (
                <button className="btn danger" onClick={() => patch({ status: "cancelled" })}>
                  Löschen
                </button>
              )}
              {a.patient && medical && (
                <button className="btn primary" onClick={startTreatment}>
                  ▶ Behandlung starten
                </button>
              )}
            </>
          )}
          {!open && a.status !== "done" && (
            <button className="btn" onClick={() => patch({ status: "planned" })}>
              Wieder aktivieren
            </button>
          )}
          {a.treatment_id && a.patient && (
            <Link to={`/patienten/${a.patient.id}/behandlungen`} className="btn" onClick={onClose}>
              Zur Behandlung
            </Link>
          )}
        </div>
      )}
    </Modal>
  );
}
