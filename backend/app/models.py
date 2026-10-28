"""Datenmodell. Medizinische Einträge werden nie physisch gelöscht, sondern storniert."""

import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class Role(str, enum.Enum):
    admin = "admin"
    therapist = "therapist"
    reception = "reception"  # Empfang: Stammdaten, Termine, Rechnungen – keine medizinischen Inhalte


class InsuranceType(str, enum.Enum):
    gkv = "gkv"
    private = "private"
    self_pay = "self_pay"
    bg = "bg"


class Sex(str, enum.Enum):
    female = "female"
    male = "male"
    diverse = "diverse"
    unknown = "unknown"


class Side(str, enum.Enum):
    left = "left"
    right = "right"
    both = "both"
    none = "none"


class DiagnosisStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"


class TreatmentStatus(str, enum.Enum):
    draft = "draft"
    final = "final"


class FindingCategory(str, enum.Enum):
    rom = "rom"  # Beweglichkeit
    strength = "strength"  # Kraft
    test = "test"  # klinischer Test (positiv/negativ)
    measure = "measure"  # sonstige Messwerte


class BodyView(str, enum.Enum):
    front = "front"
    back = "back"


class MarkKind(str, enum.Enum):
    pain = "pain"
    tension = "tension"
    numbness = "numbness"
    swelling = "swelling"
    scar = "scar"
    other = "other"


class AttachmentKind(str, enum.Enum):
    photo = "photo"
    document = "document"
    drawing = "drawing"


class GoalStatus(str, enum.Enum):
    open = "open"
    achieved = "achieved"
    dropped = "dropped"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VoidableMixin:
    voided: Mapped[bool] = mapped_column(Boolean, default=False)
    void_reason: Mapped[str | None] = mapped_column(Text)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.therapist)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setting(Base):
    """Praxis-Einstellungen als Schlüssel/Wert (Praxisname, Adresse, Bankverbindung …)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_number: Mapped[str] = mapped_column(String(16), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), index=True)
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[Sex] = mapped_column(_enum(Sex), default=Sex.unknown)

    street: Mapped[str | None] = mapped_column(String(200))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    city: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    mobile: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    occupation: Mapped[str | None] = mapped_column(String(200))
    emergency_contact: Mapped[str | None] = mapped_column(String(300))

    insurance_type: Mapped[InsuranceType] = mapped_column(_enum(InsuranceType), default=InsuranceType.gkv)
    insurance_name: Mapped[str | None] = mapped_column(String(200))
    insurance_number: Mapped[str | None] = mapped_column(String(50))
    referring_physician: Mapped[str | None] = mapped_column(String(200))

    consent_treatment: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_data_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_date: Mapped[date | None] = mapped_column(Date)

    notes: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Anamnesis(TimestampMixin, VoidableMixin, Base):
    __tablename__ = "anamneses"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_on: Mapped[date] = mapped_column(Date)

    chief_complaint: Mapped[str] = mapped_column(Text)
    onset: Mapped[str | None] = mapped_column(Text)
    current_history: Mapped[str | None] = mapped_column(Text)
    past_history: Mapped[str | None] = mapped_column(Text)
    surgeries: Mapped[str | None] = mapped_column(Text)
    medication: Mapped[str | None] = mapped_column(Text)
    pain_current: Mapped[int | None] = mapped_column(Integer)
    pain_max: Mapped[int | None] = mapped_column(Integer)
    pain_character: Mapped[str | None] = mapped_column(Text)
    aggravating_factors: Mapped[str | None] = mapped_column(Text)
    relieving_factors: Mapped[str | None] = mapped_column(Text)
    # Liste der geprüften Warnzeichen-Schlüssel, die positiv sind (siehe catalog.RED_FLAGS)
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    red_flags_notes: Mapped[str | None] = mapped_column(Text)
    activity_sport: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()


class Diagnosis(TimestampMixin, VoidableMixin, Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    icd10_code: Mapped[str | None] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)
    side: Mapped[Side] = mapped_column(_enum(Side), default=Side.none)
    diagnosed_on: Mapped[date | None] = mapped_column(Date)
    diagnosed_by: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[DiagnosisStatus] = mapped_column(_enum(DiagnosisStatus), default=DiagnosisStatus.active)
    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()


class Treatment(TimestampMixin, VoidableMixin, Base):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    diagnosis_id: Mapped[int | None] = mapped_column(ForeignKey("diagnoses.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    treated_on: Mapped[date] = mapped_column(Date, index=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)

    measures: Mapped[list[str]] = mapped_column(JSON, default=list)
    subjective: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(Text)
    pain_before: Mapped[int | None] = mapped_column(Integer)
    pain_after: Mapped[int | None] = mapped_column(Integer)
    home_exercises: Mapped[str | None] = mapped_column(Text)

    status: Mapped[TreatmentStatus] = mapped_column(_enum(TreatmentStatus), default=TreatmentStatus.draft)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[User] = relationship()
    diagnosis: Mapped[Diagnosis | None] = relationship()
    patient: Mapped[Patient] = relationship()


class AuditEntry(Base):
    """Unveränderliches Änderungsprotokoll (wer hat wann was geändert, mit Vorher/Nachher)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), index=True)
    changes: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship()


class Finding(TimestampMixin, VoidableMixin, Base):
    """Einzelner Befund-/Messwert (Beweglichkeit, Kraft, Test, Messung) – Grundlage der Verlaufsdiagramme."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    treatment_id: Mapped[int | None] = mapped_column(ForeignKey("treatments.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_on: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[FindingCategory] = mapped_column(_enum(FindingCategory))
    name: Mapped[str] = mapped_column(String(120))
    side: Mapped[Side] = mapped_column(_enum(Side), default=Side.none)
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(32))
    unit: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()


class BodyMark(TimestampMixin, VoidableMixin, Base):
    """Markierung im Körperatlas (Position relativ 0..1 auf der Vorder-/Rückansicht)."""

    __tablename__ = "body_marks"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    treatment_id: Mapped[int | None] = mapped_column(ForeignKey("treatments.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_on: Mapped[date] = mapped_column(Date, index=True)
    view: Mapped[BodyView] = mapped_column(_enum(BodyView))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    kind: Mapped[MarkKind] = mapped_column(_enum(MarkKind), default=MarkKind.pain)
    intensity: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()


class Attachment(TimestampMixin, VoidableMixin, Base):
    """Foto, Dokument (PDF) oder Stiftzeichnung. Die Datei liegt im geschützten Datenverzeichnis."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    treatment_id: Mapped[int | None] = mapped_column(ForeignKey("treatments.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("attachments.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[AttachmentKind] = mapped_column(_enum(AttachmentKind))
    caption: Mapped[str | None] = mapped_column(String(300))
    taken_on: Mapped[date] = mapped_column(Date)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(300))
    thumb_path: Mapped[str | None] = mapped_column(String(300))
    ocr_text: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()


class TherapyGoal(TimestampMixin, VoidableMixin, Base):
    __tablename__ = "therapy_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text)
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(_enum(GoalStatus), default=GoalStatus.open)
    achieved_on: Mapped[date | None] = mapped_column(Date)
    # Optional: messbares Ziel, verknüpft mit einem Befund (z. B. "LWS Flexion (FBA)" von 35 cm auf 10 cm)
    metric_name: Mapped[str | None] = mapped_column(String(120))
    metric_side: Mapped[Side] = mapped_column(_enum(Side), default=Side.none)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    target_value: Mapped[float | None] = mapped_column(Float)

    created_by: Mapped[User] = relationship()
