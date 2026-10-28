import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Patient, type PatientData } from "../api";
import { Check, ErrorBox, Select, TextArea, TextField, useForm } from "../components/fields";
import { INSURANCE, SEX, today } from "../labels";

const EMPTY: PatientData = {
  first_name: "",
  last_name: "",
  birth_date: "",
  sex: "unknown",
  street: null,
  postal_code: null,
  city: null,
  phone: null,
  mobile: null,
  email: null,
  occupation: null,
  emergency_contact: null,
  insurance_type: "gkv",
  insurance_name: null,
  insurance_number: null,
  referring_physician: null,
  consent_treatment: false,
  consent_data_processing: false,
  consent_date: null,
  notes: null,
};

export default function PatientEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [p, set, setAll] = useForm<PatientData & { archived?: boolean }>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (id) api<Patient>(`/patients/${id}`).then(setAll, (e: Error) => setError(e.message));
  }, [id, setAll]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = id
        ? await api<Patient>(`/patients/${id}`, { method: "PUT", body: { archived: false, ...p } })
        : await api<Patient>("/patients", { method: "POST", body: p });
      navigate(`/patienten/${saved.id}`, { replace: true });
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const consentGiven = p.consent_treatment || p.consent_data_processing;

  return (
    <form className="stack" onSubmit={submit}>
      <div className="page-head">
        <h1>{id ? "Stammdaten bearbeiten" : "Neuer Patient"}</h1>
      </div>

      <section className="card form-grid">
        <h2 className="wide">Person</h2>
        <TextField label="Vorname" value={p.first_name} onChange={(v) => set("first_name", v ?? "")} required autoFocus />
        <TextField label="Nachname" value={p.last_name} onChange={(v) => set("last_name", v ?? "")} required />
        <TextField label="Geburtsdatum" type="date" value={p.birth_date} onChange={(v) => set("birth_date", v ?? "")} required />
        <Select label="Geschlecht" value={p.sex} options={SEX} onChange={(v) => set("sex", v)} />
        <TextField label="Beruf" value={p.occupation} onChange={(v) => set("occupation", v)} />
      </section>

      <section className="card form-grid">
        <h2 className="wide">Kontakt</h2>
        <TextField label="Straße, Nr." value={p.street} onChange={(v) => set("street", v)} wide />
        <TextField label="PLZ" value={p.postal_code} onChange={(v) => set("postal_code", v)} />
        <TextField label="Ort" value={p.city} onChange={(v) => set("city", v)} />
        <TextField label="Telefon" type="tel" value={p.phone} onChange={(v) => set("phone", v)} />
        <TextField label="Mobil" type="tel" value={p.mobile} onChange={(v) => set("mobile", v)} />
        <TextField label="E-Mail" type="email" value={p.email} onChange={(v) => set("email", v)} />
        <TextField label="Notfallkontakt" value={p.emergency_contact} onChange={(v) => set("emergency_contact", v)} hint="Name und Telefonnummer" />
      </section>

      <section className="card form-grid">
        <h2 className="wide">Versicherung &amp; Verordnung</h2>
        <Select label="Versicherungsart" value={p.insurance_type} options={INSURANCE} onChange={(v) => set("insurance_type", v)} />
        <TextField label="Kostenträger" value={p.insurance_name} onChange={(v) => set("insurance_name", v)} />
        <TextField label="Versichertennummer" value={p.insurance_number} onChange={(v) => set("insurance_number", v)} />
        <TextField label="Verordnende/r Ärztin/Arzt" value={p.referring_physician} onChange={(v) => set("referring_physician", v)} />
      </section>

      <section className="card form-grid">
        <h2 className="wide">Einwilligungen</h2>
        <div className="wide checks">
          <Check label="Einwilligung in die Behandlung liegt vor" checked={p.consent_treatment} onChange={(v) => set("consent_treatment", v)} />
          <Check
            label="Einwilligung in die Datenverarbeitung (DSGVO) liegt vor"
            checked={p.consent_data_processing}
            onChange={(v) => {
              set("consent_data_processing", v);
              if (v && !p.consent_date) set("consent_date", today());
            }}
          />
        </div>
        {consentGiven && <TextField label="Datum der Einwilligung" type="date" value={p.consent_date} onChange={(v) => set("consent_date", v)} />}
        <TextArea label="Notizen" value={p.notes} onChange={(v) => set("notes", v)} />
        {id && <Check label="Patient archivieren (z. B. Behandlung abgeschlossen)" checked={!!p.archived} onChange={(v) => set("archived", v)} />}
      </section>

      <ErrorBox error={error} />
      <div className="actions sticky-actions">
        <button type="button" className="btn" onClick={() => navigate(-1)}>
          Abbrechen
        </button>
        <button className="btn primary big" disabled={busy}>
          Speichern
        </button>
      </div>
    </form>
  );
}
