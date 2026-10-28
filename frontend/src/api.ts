export type Role = "admin" | "therapist" | "reception";
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

export type FindingCategory = "rom" | "strength" | "test" | "measure";

export interface FindingPreset {
  category: FindingCategory;
  name: string;
  unit: string | null;
}

export interface Catalog {
  red_flags: Record<string, string>;
  measures: string[];
  finding_presets: FindingPreset[];
  test_results: string[];
}

export interface FindingData {
  recorded_on: string;
  category: FindingCategory;
  name: string;
  side: Side;
  value_num: number | null;
  value_text: string | null;
  unit: string | null;
  notes: string | null;
  treatment_id: number | null;
}
export type Finding = FindingData & MedicalMeta;

export type BodyView = "front" | "back";
export type MarkKind = "pain" | "tension" | "numbness" | "swelling" | "scar" | "other";

export interface BodyMarkData {
  recorded_on: string;
  view: BodyView;
  x: number;
  y: number;
  kind: MarkKind;
  intensity: number | null;
  note: string | null;
  treatment_id: number | null;
}
export type BodyMark = BodyMarkData & MedicalMeta;

export type AttachmentKind = "photo" | "document" | "drawing";
export interface Attachment extends MedicalMeta {
  treatment_id: number | null;
  parent_id: number | null;
  kind: AttachmentKind;
  caption: string | null;
  taken_on: string;
  filename: string;
  content_type: string;
  size: number;
  has_thumb: boolean;
  ocr_text: string | null;
}

export type GoalStatus = "open" | "achieved" | "dropped";
export interface GoalData {
  description: string;
  target_date: string | null;
  status: GoalStatus;
  achieved_on: string | null;
  metric_name: string | null;
  metric_side: Side;
  baseline_value: number | null;
  target_value: number | null;
}
export type Goal = GoalData & MedicalMeta;

export interface PracticeSettings {
  practice_name: string | null;
  practice_owner: string | null;
  practice_address: string | null;
  practice_phone: string | null;
  practice_email: string | null;
  practice_tax_number: string | null;
  practice_ik: string | null;
  practice_iban: string | null;
  practice_bic: string | null;
  practice_bank: string | null;
  invoice_vat_note: string | null;
  invoice_payment_days: string | null;
  invoice_footer: string | null;
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

async function fail(res: Response): Promise<never> {
  let message = res.statusText;
  try {
    message = describe((await res.json()).detail);
  } catch {
    /* keine JSON-Antwort */
  }
  throw new ApiError(res.status, message);
}

/** Multipart-Upload (Fotos, Dokumente, Zeichnungen, Audio). */
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api${path}`, { method: "POST", credentials: "same-origin", headers: { "X-PhysioFlow": "1" }, body: form });
  if (res.status === 401) window.dispatchEvent(new Event("physioflow:unauthorized"));
  if (!res.ok) return fail(res);
  return res.json();
}

/** Lädt eine Binärdatei (z. B. PDF) per POST und öffnet sie in einem neuen Tab. */
export async function openPdf(path: string, body: unknown): Promise<void> {
  const win = window.open("", "_blank");
  try {
    const res = await fetch(`/api${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-PhysioFlow": "1", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return await fail(res);
    const url = URL.createObjectURL(await res.blob());
    if (win) win.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 5 * 60_000);
  } catch (e) {
    win?.close();
    throw e;
  }
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
