import { useState, type FormEvent } from "react";
import { api, type Appointment, type FollowUp, type PatientListItem } from "../api";
import { useApi } from "../hooks";
import { APPT_STATUS, WEEKDAY, formatDate, formatTime, today } from "../labels";
import { AppointmentDialog, NewAppointmentDialog } from "./AppointmentDialog";
import { ErrorBox, TextField } from "./fields";

/** Kommende Termine und Wiedervorlagen eines Patienten (Übersichtsreiter). */
export default function AgendaCard({ patient }: { patient: PatientListItem }) {
  const now = new Date();
  const appts = useApi<Appointment[]>(`/appointments?${new URLSearchParams({ start: new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString(), end: new Date(now.getFullYear() + 1, now.getMonth(), now.getDate()).toISOString(), patient_id: String(patient.id) })}`);
  const followUps = useApi<FollowUp[]>(`/follow-ups?${new URLSearchParams({ patient_id: String(patient.id) })}`);
  const [open, setOpen] = useState<Appointment | null>(null);
  const [creating, setCreating] = useState(false);
  const [due, setDue] = useState(today());
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const upcoming = (appts.data ?? []).filter((a) => a.status === "planned");

  async function addFollowUp(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api(`/patients/${patient.id}/follow-ups`, { method: "POST", body: { due_on: due, text } });
      setText("");
      followUps.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function done(f: FollowUp) {
    await api(`/follow-ups/${f.id}`, { method: "PATCH", body: { done: true } });
    followUps.reload();
  }

  return (
    <section className="card">
      <div className="page-head">
        <h2>Termine &amp; Wiedervorlagen</h2>
        <button className="btn small primary" onClick={() => setCreating(true)}>
          + Termin
        </button>
      </div>
      {upcoming.length === 0 ? (
        <p className="muted">Kein kommender Termin.</p>
      ) : (
        <ul className="list">
          {upcoming.slice(0, 6).map((a) => (
            <li key={a.id}>
              <button className="link-btn row-btn" onClick={() => setOpen(a)}>
                <span>
                  <strong>
                    {WEEKDAY[new Date(a.start).getDay()]} {formatDate(a.start)}, {formatTime(a.start)} Uhr
                  </strong>
                  <span className="muted block">
                    {a.therapist.full_name}
                    {a.prescription_label ? ` · ${a.prescription_label}` : ""} · {APPT_STATUS[a.status]}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <h3>Wiedervorlagen</h3>
      <ul className="list">
        {(followUps.data ?? []).map((f) => (
          <li key={f.id} className="follow">
            <span>
              <strong className={f.due_on <= today() ? "danger-text" : undefined}>{formatDate(f.due_on)}</strong> – {f.text}
            </span>
            <button className="btn small" onClick={() => done(f)}>
              ✓ Erledigt
            </button>
          </li>
        ))}
      </ul>
      <form className="follow-form" onSubmit={addFollowUp}>
        <TextField label="Fällig am" type="date" value={due} onChange={(v) => setDue(v ?? "")} required />
        <TextField label="Wiedervorlage" value={text} onChange={(v) => setText(v ?? "")} required placeholder="z. B. Folgeverordnung anfragen" />
        <button className="btn">Hinzufügen</button>
      </form>
      <ErrorBox error={error} />
      {open && <AppointmentDialog appointment={open} onClose={() => setOpen(null)} onChanged={appts.reload} />}
      {creating && <NewAppointmentDialog start={defaultStart()} patient={patient} onClose={() => setCreating(false)} onSaved={appts.reload} />}
    </section>
  );
}

function defaultStart(): Date {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  return d;
}
