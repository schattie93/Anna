from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from .catalog import RED_FLAGS
from .models import DiagnosisStatus, InsuranceType, Role, Sex, Side, TreatmentStatus

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


class Catalog(BaseModel):
    red_flags: dict[str, str]
    measures: list[str]
