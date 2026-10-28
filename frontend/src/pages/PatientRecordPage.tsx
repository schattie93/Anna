import { Link, NavLink, useParams } from "react-router-dom";
import { useState } from "react";
import type { Anamnesis, Attachment, BodyMark, Diagnosis, Finding, Goal, Patient, Treatment } from "../api";
import { useUser } from "../auth";
import { ErrorBox } from "../components/fields";
import { useApi, useCatalog } from "../hooks";
import { INSURANCE, SIDE, age, formatDate } from "../labels";
import AnamnesisTab from "./record/AnamnesisTab";
import AtlasTab from "./record/AtlasTab";
import DiagnosesTab from "./record/DiagnosesTab";
import FilesTab from "./record/FilesTab";
import FindingsTab from "./record/FindingsTab";
import GoalsTab from "./record/GoalsTab";
import HistoryTab from "./record/HistoryTab";
import OverviewTab from "./record/OverviewTab";
import ReportDialog from "./record/ReportDialog";
import TreatmentsTab from "./record/TreatmentsTab";

const TABS = [
  ["", "Übersicht"],
  ["anamnese", "Anamnese"],
  ["diagnosen", "Diagnosen"],
  ["befunde", "Befunde"],
  ["koerperatlas", "Körperatlas"],
  ["behandlungen", "Behandlungen"],
  ["dateien", "Bilder & Dokumente"],
  ["ziele", "Ziele"],
  ["protokoll", "Änderungsprotokoll"],
] as const;

export default function PatientRecordPage() {
  const { id, tab = "" } = useParams();
  const medical = useUser().role !== "reception";
  const [reporting, setReporting] = useState(false);
  const base = medical ? `/patients/${id}` : null;
  const patient = useApi<Patient>(`/patients/${id}`);
  const anamneses = useApi<Anamnesis[]>(base && `${base}/anamneses`);
  const diagnoses = useApi<Diagnosis[]>(base && `${base}/diagnoses`);
  const treatments = useApi<Treatment[]>(base && `${base}/treatments`);
  const findings = useApi<Finding[]>(base && `${base}/findings`);
  const goals = useApi<Goal[]>(base && `${base}/goals`);
  const marks = useApi<BodyMark[]>(base && tab === "koerperatlas" ? `${base}/body-marks` : null);
  const files = useApi<Attachment[]>(base && tab === "dateien" ? `${base}/attachments` : null);
  const catalog = useCatalog();

  if (patient.error) return <ErrorBox error={patient.error} />;
  const p = patient.data;
  if (!p || !catalog) return <p className="muted">Lade Patientenakte …</p>;
  if (medical && (!anamneses.data || !diagnoses.data || !treatments.data || !findings.data || !goals.data)) return <p className="muted">Lade Patientenakte …</p>;
  const tabs = medical ? TABS : TABS.slice(0, 1);

  const latestAnamnesis = anamneses.data?.find((a) => !a.voided);
  const redFlags = latestAnamnesis?.red_flags ?? [];
  const primary = diagnoses.data?.find((d) => d.is_primary && !d.voided);
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
          <div className="actions">
            {medical && (
              <button className="btn" onClick={() => setReporting(true)}>
                Bericht (PDF)
              </button>
            )}
            <Link to={`/patienten/${p.id}/bearbeiten`} className="btn">
              Stammdaten bearbeiten
            </Link>
          </div>
        </div>
      </section>

      <nav className="tabs">
        {tabs.map(([slug, label]) => (
          <NavLink key={slug} to={`/patienten/${p.id}${slug ? "/" + slug : ""}`} end>
            {label}
          </NavLink>
        ))}
      </nav>

      {tab === "" && (
        <OverviewTab patient={p} anamnesis={latestAnamnesis} diagnoses={diagnoses.data ?? []} treatments={treatments.data ?? []} catalog={catalog} medical={medical} />
      )}
      {medical && tab === "anamnese" && <AnamnesisTab {...ctx} entries={anamneses.data!} reload={anamneses.reload} />}
      {medical && tab === "diagnosen" && <DiagnosesTab {...ctx} entries={diagnoses.data!} reload={diagnoses.reload} />}
      {medical && tab === "befunde" && <FindingsTab {...ctx} entries={findings.data!} reload={findings.reload} />}
      {medical && tab === "koerperatlas" && <AtlasTab patientId={p.id} entries={marks.data ?? []} reload={marks.reload} />}
      {medical && tab === "behandlungen" && <TreatmentsTab {...ctx} entries={treatments.data!} diagnoses={diagnoses.data!} reload={treatments.reload} />}
      {medical && tab === "dateien" && <FilesTab patientId={p.id} entries={files.data ?? []} reload={files.reload} />}
      {medical && tab === "ziele" && <GoalsTab patientId={p.id} entries={goals.data!} findings={findings.data!} reload={goals.reload} />}
      {medical && tab === "protokoll" && <HistoryTab patientId={p.id} />}
      {reporting && <ReportDialog patientId={p.id} defaultRecipient={p.referring_physician} onClose={() => setReporting(false)} />}
    </div>
  );
}
