from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from .catalog import RED_FLAGS, TEST_RESULTS
from .models import (
    AttachmentKind,
    BodyView,
    DiagnosisStatus,
    FindingCategory,
    GoalStatus,
    InsuranceType,
    MarkKind,
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


class Dashboard(BaseModel):
    patient_count: int
    treatments_today: int
    open_treatments: list[OpenTreatment]
    recent_patients: list[PatientListItem]


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
