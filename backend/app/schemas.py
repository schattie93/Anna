from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from .catalog import RED_FLAGS, TEST_RESULTS
from .models import (
    AppointmentStatus,
    AttachmentKind,
    BodyView,
    DiagnosisStatus,
    FindingCategory,
    GoalStatus,
    InsuranceType,
    InvoiceStatus,
    MarkKind,
    PaymentMethod,
    Role,
    Sex,
    Side,
    TreatmentStatus,
)

Pain = Annotated[int, Field(ge=0, le=10)]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth & Benutzer ---------------------------------------------------------


class LoginIn(BaseModel):
    username: str
    password: str


class SetupIn(BaseModel):
    username: NonEmpty
    full_name: NonEmpty
    password: Annotated[str, Field(min_length=10)]


class UserOut(ORM):
    id: int
    username: str
    full_name: str
    role: Role
    is_active: bool


class UserCreate(SetupIn):
    role: Role = Role.therapist


class UserUpdate(BaseModel):
    full_name: NonEmpty | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: Annotated[str, Field(min_length=10)] | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: Annotated[str, Field(min_length=10)]


class AuthStatus(BaseModel):
    setup_required: bool
    user: UserOut | None


# --- Patienten ---------------------------------------------------------------


class PatientBase(BaseModel):
    first_name: NonEmpty
    last_name: NonEmpty
    birth_date: date
    sex: Sex = Sex.unknown
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: EmailStr | None = None
    occupation: str | None = None
    emergency_contact: str | None = None
    insurance_type: InsuranceType = InsuranceType.gkv
    insurance_name: str | None = None
    insurance_number: str | None = None
    referring_physician: str | None = None
    consent_treatment: bool = False
    consent_data_processing: bool = False
    consent_date: date | None = None
    notes: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_is_none(cls, v):
        return v or None

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Geburtsdatum liegt in der Zukunft")
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(PatientBase):
    archived: bool = False


class PatientOut(ORM, PatientBase):
    id: int
    patient_number: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class PatientListItem(ORM):
    id: int
    patient_number: str
    first_name: str
    last_name: str
    birth_date: date
    city: str | None
    insurance_type: InsuranceType
    archived: bool


# --- Gemeinsam für medizinische Einträge ---------------------------------------


class VoidIn(BaseModel):
    reason: NonEmpty


class Author(ORM):
    id: int
    full_name: str


class MedicalOut(ORM):
    id: int
    patient_id: int
    created_by: Author
    created_at: datetime
    updated_at: datetime
    voided: bool
    void_reason: str | None
    voided_at: datetime | None


# --- Anamnese ----------------------------------------------------------------


class AnamnesisBase(BaseModel):
    recorded_on: date
    chief_complaint: NonEmpty
    onset: str | None = None
    current_history: str | None = None
    past_history: str | None = None
    surgeries: str | None = None
    medication: str | None = None
    pain_current: Pain | None = None
    pain_max: Pain | None = None
    pain_character: str | None = None
    aggravating_factors: str | None = None
    relieving_factors: str | None = None
    red_flags: list[str] = []
    red_flags_notes: str | None = None
    activity_sport: str | None = None
    goals: str | None = None

    @field_validator("red_flags")
    @classmethod
    def known_red_flags(cls, v: list[str]) -> list[str]:
        unknown = set(v) - RED_FLAGS.keys()
        if unknown:
            raise ValueError(f"Unbekannte Warnzeichen: {', '.join(sorted(unknown))}")
        return sorted(set(v))


class AnamnesisIn(AnamnesisBase):
    pass


class AnamnesisUpdate(AnamnesisBase):
    correction_reason: NonEmpty


class AnamnesisOut(MedicalOut, AnamnesisBase):
    pass


# --- Diagnosen ---------------------------------------------------------------


class DiagnosisBase(BaseModel):
    icd10_code: str | None = None
    description: NonEmpty
    side: Side = Side.none
    diagnosed_on: date | None = None
    diagnosed_by: str | None = None
    is_primary: bool = False
    status: DiagnosisStatus = DiagnosisStatus.active
    notes: str | None = None

    @field_validator("icd10_code")
    @classmethod
    def normalize_icd(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().upper() or None


class DiagnosisIn(DiagnosisBase):
    pass


class DiagnosisUpdate(DiagnosisBase):
    correction_reason: str | None = None


class DiagnosisOut(MedicalOut, DiagnosisBase):
    pass


# --- Behandlungen ------------------------------------------------------------


class TreatmentBase(BaseModel):
    treated_on: date
    diagnosis_id: int | None = None
    prescription_id: int | None = None
    duration_minutes: Annotated[int, Field(ge=1, le=480)] | None = None
    measures: list[str] = []
    subjective: str | None = None
    objective: str | None = None
    assessment: str | None = None
    plan: str | None = None
    pain_before: Pain | None = None
    pain_after: Pain | None = None
    home_exercises: str | None = None


class TreatmentIn(TreatmentBase):
    finalize: bool = False


class TreatmentUpdate(TreatmentBase):
    finalize: bool = False
    # Pflicht, sobald eine bereits abgeschlossene Behandlung korrigiert wird.
    correction_reason: str | None = None


class TreatmentOut(MedicalOut, TreatmentBase):
    status: TreatmentStatus
    finalized_at: datetime | None


class OpenTreatment(ORM):
    id: int
    patient_id: int
    treated_on: date
    patient: PatientListItem


# --- Protokoll / Dashboard ---------------------------------------------------


class AuditOut(ORM):
    id: int
    at: datetime
    user: Author | None
    action: str
    entity_type: str
    entity_id: int | None
    patient_id: int | None
    changes: dict | None
    reason: str | None


class RxAttention(BaseModel):
    patient: PatientListItem
    prescription_id: int
    measure: str
    units_done: int
    total_units: int
    warnings: list["RxWarning"]


class Dashboard(BaseModel):
    patient_count: int
    treatments_today: int
    open_treatments: list[OpenTreatment]
    recent_patients: list[PatientListItem]
    appointments_today: list["AppointmentOut"] = []
    follow_ups_due: list["FollowUpOut"] = []
    rx_attention: list[RxAttention] = []


class FindingPreset(BaseModel):
    category: FindingCategory
    name: str
    unit: str | None


class Catalog(BaseModel):
    red_flags: dict[str, str]
    measures: list[str]
    finding_presets: list[FindingPreset]
    test_results: list[str]


# --- Befunde -----------------------------------------------------------------


class FindingBase(BaseModel):
    recorded_on: date
    category: FindingCategory
    name: NonEmpty
    side: Side = Side.none
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    notes: str | None = None
    treatment_id: int | None = None

    @model_validator(mode="after")
    def value_matches_category(self):
        if self.category == FindingCategory.test:
            if self.value_text not in TEST_RESULTS:
                raise ValueError("Testergebnis muss positiv, negativ oder fraglich sein")
            self.value_num = None
        else:
            if self.value_num is None:
                raise ValueError("Messwert fehlt")
            self.value_text = None
        return self


class FindingIn(FindingBase):
    pass


class FindingUpdate(FindingBase):
    correction_reason: NonEmpty


class FindingOut(MedicalOut, FindingBase):
    pass


# --- Körperatlas ---------------------------------------------------------------


class BodyMarkBase(BaseModel):
    recorded_on: date
    view: BodyView
    x: Annotated[float, Field(ge=0, le=1)]
    y: Annotated[float, Field(ge=0, le=1)]
    kind: MarkKind = MarkKind.pain
    intensity: Pain | None = None
    note: str | None = None
    treatment_id: int | None = None


class BodyMarkIn(BodyMarkBase):
    pass


class BodyMarkUpdate(BodyMarkBase):
    pass


class BodyMarkOut(MedicalOut, BodyMarkBase):
    pass


# --- Dateien -------------------------------------------------------------------


class AttachmentOut(MedicalOut):
    treatment_id: int | None
    parent_id: int | None
    kind: AttachmentKind
    caption: str | None
    taken_on: date
    filename: str
    content_type: str
    size: int
    has_thumb: bool = False
    ocr_text: str | None


class AttachmentUpdate(BaseModel):
    caption: str | None = None
    taken_on: date | None = None
    treatment_id: int | None = None
    ocr_text: str | None = None


# --- Therapieziele ---------------------------------------------------------------


class GoalBase(BaseModel):
    description: NonEmpty
    target_date: date | None = None
    status: GoalStatus = GoalStatus.open
    achieved_on: date | None = None
    metric_name: str | None = None
    metric_side: Side = Side.none
    baseline_value: float | None = None
    target_value: float | None = None


class GoalIn(GoalBase):
    pass


class GoalUpdate(GoalBase):
    pass


class GoalOut(MedicalOut, GoalBase):
    pass


class ReportIn(BaseModel):
    summary: str | None = None
    recipient: str | None = None
    from_date: date | None = None
    to_date: date | None = None


class PracticeSettings(BaseModel):
    practice_name: str | None = None
    practice_owner: str | None = None
    practice_address: str | None = None
    practice_phone: str | None = None
    practice_email: str | None = None
    practice_tax_number: str | None = None
    practice_ik: str | None = None
    practice_iban: str | None = None
    practice_bic: str | None = None
    practice_bank: str | None = None
    invoice_vat_note: str | None = None
    invoice_payment_days: str | None = None
    invoice_footer: str | None = None


# --- Verordnungen --------------------------------------------------------------


class PrescriptionBase(BaseModel):
    issued_on: date
    physician: str | None = None
    diagnosis_text: str | None = None
    icd10_code: str | None = None
    indication_key: str | None = None
    measure: NonEmpty
    total_units: Annotated[int, Field(ge=1, le=60)]
    frequency: str | None = None
    urgent: bool = False
    home_visit: bool = False
    notes: str | None = None


class PrescriptionIn(PrescriptionBase):
    pass


class PrescriptionUpdate(PrescriptionBase):
    correction_reason: str | None = None


class RxWarning(BaseModel):
    level: str
    text: str


class PrescriptionOut(MedicalOut, PrescriptionBase):
    units_done: int = 0
    units_remaining: int = 0
    status: str = "open"
    latest_start: date | None = None
    warnings: list[RxWarning] = []


# --- Termine & Wiedervorlagen ---------------------------------------------------


class AppointmentIn(BaseModel):
    patient_id: int | None = None
    therapist_id: int | None = None
    prescription_id: int | None = None
    start: datetime
    duration_minutes: Annotated[int, Field(ge=5, le=480)] = 30
    title: str | None = None
    note: str | None = None
    repeat_count: Annotated[int, Field(ge=1, le=52)] = 1
    repeat_days: Annotated[int, Field(ge=1, le=60)] = 7
    force: bool = False

    @model_validator(mode="after")
    def patient_or_title(self):
        if self.patient_id is None and not (self.title or "").strip():
            raise ValueError("Termin braucht einen Patienten oder eine Bezeichnung (Blockzeit)")
        return self


class AppointmentUpdate(BaseModel):
    start: datetime | None = None
    duration_minutes: Annotated[int, Field(ge=5, le=480)] | None = None
    status: AppointmentStatus | None = None
    prescription_id: int | None = None
    title: str | None = None
    note: str | None = None
    cancel_reason: str | None = None
    force: bool = False


class AppointmentOut(ORM):
    id: int
    patient: PatientListItem | None
    therapist: Author
    prescription_id: int | None
    prescription_label: str | None = None
    treatment_id: int | None
    start: datetime
    end: datetime
    status: AppointmentStatus
    title: str | None
    note: str | None
    cancel_reason: str | None


class SkippedAppointment(BaseModel):
    start: datetime
    reason: str


class AppointmentCreated(BaseModel):
    created: list[AppointmentOut]
    skipped: list[SkippedAppointment]


class ReminderOut(BaseModel):
    appointment: AppointmentOut
    phone: str | None
    mobile: str | None


class FollowUpIn(BaseModel):
    due_on: date
    text: NonEmpty


class FollowUpOut(ORM):
    id: int
    patient: PatientListItem
    due_on: date
    text: str
    done: bool
    done_at: datetime | None
    created_by: Author


# --- Übungen --------------------------------------------------------------------


class ExerciseBase(BaseModel):
    title: NonEmpty
    region: str | None = None
    description: str | None = None
    instructions: str | None = None
    default_sets: Annotated[int, Field(ge=1, le=20)] | None = None
    default_reps: Annotated[int, Field(ge=1, le=200)] | None = None
    default_hold_seconds: Annotated[int, Field(ge=1, le=600)] | None = None


class ExerciseIn(ExerciseBase):
    pass


class ExerciseUpdate(ExerciseBase):
    archived: bool = False


class ExerciseOut(ORM, ExerciseBase):
    id: int
    archived: bool
    has_image: bool = False


class PlanItemBase(BaseModel):
    exercise_id: int | None = None
    title: NonEmpty
    instructions: str | None = None
    sets: Annotated[int, Field(ge=1, le=20)] | None = None
    reps: Annotated[int, Field(ge=1, le=200)] | None = None
    hold_seconds: Annotated[int, Field(ge=1, le=600)] | None = None
    frequency: str | None = None
    notes: str | None = None


class PlanItemOut(ORM, PlanItemBase):
    id: int
    position: int
    has_image: bool = False


class ExercisePlanIn(BaseModel):
    title: NonEmpty
    issued_on: date
    notes: str | None = None
    items: Annotated[list[PlanItemBase], Field(min_length=1, max_length=40)]


class ExercisePlanOut(MedicalOut):
    title: str
    issued_on: date
    notes: str | None
    items: list[PlanItemOut]


Dashboard.model_rebuild()
RxAttention.model_rebuild()


# --- Lokale Assistenz ---------------------------------------------------------------


class AssistStatus(BaseModel):
    transcribe: bool
    ocr: bool
    suggest: bool


class TextOut(BaseModel):
    text: str


class SuggestIn(BaseModel):
    task: str
    text: Annotated[str, StringConstraints(min_length=1, max_length=20000)]


class SoapOut(BaseModel):
    subjective: str | None
    objective: str | None
    assessment: str | None
    plan: str | None
    notice: str = "KI-Entwurf – bitte vollständig prüfen, bevor er übernommen wird."


class DraftOut(BaseModel):
    text: str
    notice: str = "KI-Entwurf – bitte vollständig prüfen, bevor er übernommen wird."


# --- Abrechnung ------------------------------------------------------------------


class ServiceIn(BaseModel):
    code: str | None = None
    name: NonEmpty
    price_cents: Annotated[int, Field(ge=0, le=10_000_000)]
    active: bool = True


class ServiceOut(ORM, ServiceIn):
    id: int


class InvoiceItemIn(BaseModel):
    treatment_id: int | None = None
    service_date: date
    description: NonEmpty
    quantity: Annotated[int, Field(ge=1, le=999)] = 1
    unit_price_cents: Annotated[int, Field(ge=0, le=10_000_000)]


class InvoiceItemOut(ORM):
    id: int
    treatment_id: int | None
    service_date: date
    description: str
    quantity: int
    unit_price_cents: int
    total_cents: int


class PaymentIn(BaseModel):
    paid_on: date
    amount_cents: Annotated[int, Field(gt=0, le=10_000_000)]
    method: PaymentMethod = PaymentMethod.transfer
    note: str | None = None


class PaymentOut(ORM):
    id: int
    paid_on: date
    amount_cents: int
    method: PaymentMethod
    note: str | None
    voided: bool
    void_reason: str | None
    created_by: Author


class InvoiceDraftIn(BaseModel):
    recipient_name: NonEmpty
    recipient_address: str | None = None
    note: str | None = None
    items: Annotated[list[InvoiceItemIn], Field(min_length=1, max_length=200)]


class InvoiceFromTreatments(BaseModel):
    patient_id: int
    treatment_ids: Annotated[list[int], Field(min_length=1, max_length=100)]
    service_id: int
    recipient_name: str | None = None
    recipient_address: str | None = None


class InvoiceOut(ORM):
    id: int
    number: str | None
    status: InvoiceStatus
    patient: PatientListItem
    recipient_name: str
    recipient_address: str | None
    issue_date: date | None
    due_date: date | None
    note: str | None
    vat_note: str | None
    total_cents: int
    paid_cents: int
    cancels_id: int | None
    items: list[InvoiceItemOut]
    payments: list[PaymentOut]
    created_by: Author
    overdue: bool = False


class InvoiceListItem(ORM):
    id: int
    number: str | None
    status: InvoiceStatus
    patient: PatientListItem
    issue_date: date | None
    due_date: date | None
    total_cents: int
    paid_cents: int
    cancels_id: int | None
    overdue: bool = False


class BillableTreatment(BaseModel):
    treatment_id: int
    treated_on: date
    duration_minutes: int | None
    measures: list[str]
    prescription_label: str | None


class GkvRow(BaseModel):
    prescription_id: int
    patient: PatientListItem
    insurance_name: str | None
    insurance_number: str | None
    issued_on: date
    physician: str | None
    icd10_code: str | None
    indication_key: str | None
    measure: str
    total_units: int
    units_done: int
    treatment_dates: list[date]
    problems: list[str]
    ready: bool
