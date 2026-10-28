import { Link, NavLink, useParams } from "react-router-dom";
import type { Anamnesis, Diagnosis, Patient, Treatment } from "../api";
import { ErrorBox } from "../components/fields";
import { useApi, useCatalog } from "../hooks";
import { INSURANCE, SIDE, age, formatDate } from "../labels";
import AnamnesisTab from "./record/AnamnesisTab";
import DiagnosesTab from "./record/DiagnosesTab";
import HistoryTab from "./record/HistoryTab";
import OverviewTab from "./record/OverviewTab";
import TreatmentsTab from "./record/TreatmentsTab";

const TABS = [
  ["", "Übersicht"],
  ["anamnese", "Anamnese"],
  ["diagnosen", "Diagnosen"],
  ["behandlungen", "Behandlungen"],
  ["protokoll", "Änderungsprotokoll"],
] as const;

export default function PatientRecordPage() {
  const { id, tab = "" } = useParams();
  const patient = useApi<Patient>(`/patients/${id}`);
  const anamneses = useApi<Anamnesis[]>(`/patients/${id}/anamneses`);
  const diagnoses = useApi<Diagnosis[]>(`/patients/${id}/diagnoses`);
  const treatments = useApi<Treatment[]>(`/patients/${id}/treatments`);
  const catalog = useCatalog();

  if (patient.error) return <ErrorBox error={patient.error} />;
  const p = patient.data;
  if (!p || !anamneses.data || !diagnoses.data || !treatments.data || !catalog) return <p className="muted">Lade Patientenakte …</p>;

  const latestAnamnesis = anamneses.data.find((a) => !a.voided);
  const redFlags = latestAnamnesis?.red_flags ?? [];
  const primary = diagnoses.data.find((d) => d.is_primary && !d.voided);
  const ctx = { patientId: p.id, catalog };

  return (
    <div className="stack">
      <section className="card patient-head">
        <div>
          <h1>
            {p.last_name}, {p.first_name}
            {p.archived && <span className="badge">archiviert</span>}
          </h1>
          <p className="muted">
            {p.patient_number} · geb. {formatDate(p.birth_date)} ({age(p.birth_date)} J.) · {INSURANCE[p.insurance_type]}
            {p.insurance_name ? ` – ${p.insurance_name}` : ""}
          </p>
          {primary && (
            <p>
              <strong>Hauptdiagnose:</strong> {primary.description}
              {primary.icd10_code && ` (${primary.icd10_code})`}
              {primary.side !== "none" && `, ${SIDE[primary.side]}`}
            </p>
          )}
        </div>
        <div className="head-side">
          {!p.consent_data_processing && <span className="badge warn">Einwilligung Datenverarbeitung fehlt</span>}
          {redFlags.length > 0 && (
            <span className="badge danger" title={redFlags.map((f) => catalog.red_flags[f]).join(", ")}>
              ⚠ {redFlags.length} Warnzeichen
            </span>
          )}
          <Link to={`/patienten/${p.id}/bearbeiten`} className="btn">
            Stammdaten bearbeiten
          </Link>
        </div>
      </section>

      <nav className="tabs">
        {TABS.map(([slug, label]) => (
          <NavLink key={slug} to={`/patienten/${p.id}${slug ? "/" + slug : ""}`} end>
            {label}
          </NavLink>
        ))}
      </nav>

      {tab === "" && <OverviewTab patient={p} anamnesis={latestAnamnesis} diagnoses={diagnoses.data} treatments={treatments.data} catalog={catalog} />}
      {tab === "anamnese" && <AnamnesisTab {...ctx} entries={anamneses.data} reload={anamneses.reload} />}
      {tab === "diagnosen" && <DiagnosesTab {...ctx} entries={diagnoses.data} reload={diagnoses.reload} />}
      {tab === "behandlungen" && (
        <TreatmentsTab {...ctx} entries={treatments.data} diagnoses={diagnoses.data} reload={treatments.reload} />
      )}
      {tab === "protokoll" && <HistoryTab patientId={p.id} />}
    </div>
  );
}
