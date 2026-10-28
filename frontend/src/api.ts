export type Role = "admin" | "therapist";
export type Sex = "female" | "male" | "diverse" | "unknown";
export type InsuranceType = "gkv" | "private" | "self_pay" | "bg";
export type Side = "left" | "right" | "both" | "none";

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface AuthStatus {
  setup_required: boolean;
  user: User | null;
}

export interface PatientData {
  first_name: string;
  last_name: string;
  birth_date: string;
  sex: Sex;
  street: string | null;
  postal_code: string | null;
  city: string | null;
  phone: string | null;
  mobile: string | null;
  email: string | null;
  occupation: string | null;
  emergency_contact: string | null;
  insurance_type: InsuranceType;
  insurance_name: string | null;
  insurance_number: string | null;
  referring_physician: string | null;
  consent_treatment: boolean;
  consent_data_processing: boolean;
  consent_date: string | null;
  notes: string | null;
}

export interface Patient extends PatientData {
  id: number;
  patient_number: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface PatientListItem {
  id: number;
  patient_number: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  city: string | null;
  insurance_type: InsuranceType;
  archived: boolean;
}

export interface MedicalMeta {
  id: number;
  patient_id: number;
  created_by: { id: number; full_name: string };
  created_at: string;
  updated_at: string;
  voided: boolean;
  void_reason: string | null;
  voided_at: string | null;
}

export interface AnamnesisData {
  recorded_on: string;
  chief_complaint: string;
  onset: string | null;
  current_history: string | null;
  past_history: string | null;
  surgeries: string | null;
  medication: string | null;
  pain_current: number | null;
  pain_max: number | null;
  pain_character: string | null;
  aggravating_factors: string | null;
  relieving_factors: string | null;
  red_flags: string[];
  red_flags_notes: string | null;
  activity_sport: string | null;
  goals: string | null;
}
export type Anamnesis = AnamnesisData & MedicalMeta;

export interface DiagnosisData {
  icd10_code: string | null;
  description: string;
  side: Side;
  diagnosed_on: string | null;
  diagnosed_by: string | null;
  is_primary: boolean;
  status: "active" | "resolved";
  notes: string | null;
}
export type Diagnosis = DiagnosisData & MedicalMeta;

export interface TreatmentData {
  treated_on: string;
  diagnosis_id: number | null;
  duration_minutes: number | null;
  measures: string[];
  subjective: string | null;
  objective: string | null;
  assessment: string | null;
  plan: string | null;
  pain_before: number | null;
  pain_after: number | null;
  home_exercises: string | null;
}
export type Treatment = TreatmentData &
  MedicalMeta & { status: "draft" | "final"; finalized_at: string | null };

export interface AuditEntry {
  id: number;
  at: string;
  user: { id: number; full_name: string } | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  patient_id: number | null;
  changes: Record<string, unknown> | null;
  reason: string | null;
}

export interface Dashboard {
  patient_count: number;
  treatments_today: number;
  open_treatments: { id: number; patient_id: number; treated_on: string; patient: PatientListItem }[];
  recent_patients: PatientListItem[];
}

export interface Catalog {
  red_flags: Record<string, string>;
  measures: string[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = d.loc?.filter((x) => x !== "body").join(".");
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return "Unbekannter Fehler";
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: options.method ?? "GET",
    credentials: "same-origin",
    headers: {
      "X-PhysioFlow": "1",
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 401 && path !== "/auth/login" && path !== "/auth/status") {
    window.dispatchEvent(new Event("physioflow:unauthorized"));
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      message = describe((await res.json()).detail);
    } catch {
      /* keine JSON-Antwort */
    }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}
