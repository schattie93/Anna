"""Datenmodell. Medizinische Einträge werden nie physisch gelöscht, sondern storniert."""

import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    signature = "signature"  # Unterschrift des Patienten (Leistungsnachweis je Behandlung)


class GoalStatus(str, enum.Enum):
    open = "open"
    achieved = "achieved"
    dropped = "dropped"


class AppointmentStatus(str, enum.Enum):
    planned = "planned"
    done = "done"
    cancelled = "cancelled"  # abgesagt
    no_show = "no_show"  # nicht erschienen


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"  # gestellt, offen
    paid = "paid"
    cancelled = "cancelled"  # storniert (durch Stornorechnung)


class PaymentMethod(str, enum.Enum):
    transfer = "transfer"
    cash = "cash"
    card = "card"


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
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    yellow_flags: Mapped[list[str]] = mapped_column(JSON, default=list)  # psychosoziale Risikofaktoren
    social_history: Mapped[str | None] = mapped_column(Text)  # Beruf, Familie, Wohnsituation, Belastungen
    sleep: Mapped[str | None] = mapped_column(Text)
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
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"))
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
    # Neutral-Null-Methode: Gegenrichtung und Mittelwert (z. B. Knie Extension 0 - Neutral 0 - Flexion 130)
    value_opposite: Mapped[float | None] = mapped_column(Float)
    value_neutral: Mapped[float | None] = mapped_column(Float)
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


class Prescription(TimestampMixin, VoidableMixin, Base):
    """Heilmittelverordnung. Verbrauchte Einheiten ergeben sich aus den verknüpften, abgeschlossenen Behandlungen."""

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    issued_on: Mapped[date] = mapped_column(Date)
    physician: Mapped[str | None] = mapped_column(String(200))
    diagnosis_text: Mapped[str | None] = mapped_column(Text)
    icd10_code: Mapped[str | None] = mapped_column(String(16))
    diagnosis_group: Mapped[str | None] = mapped_column(String(16))  # Diagnosegruppe laut Katalog, z. B. WS
    indication_key: Mapped[str | None] = mapped_column(String(16))  # Indikationsschlüssel, z. B. WS1
    leitsymptomatik: Mapped[str | None] = mapped_column(String(16))  # z. B. a, b, c, x
    measure: Mapped[str] = mapped_column(String(120))  # verordnetes Heilmittel
    total_units: Mapped[int] = mapped_column(Integer)
    frequency: Mapped[str | None] = mapped_column(String(64))  # z. B. 2x pro Woche
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)  # dringlicher Behandlungsbedarf
    home_visit: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), index=True)  # leer = Blockzeit
    therapist_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"))
    treatment_id: Mapped[int | None] = mapped_column(ForeignKey("treatments.id"))
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(_enum(AppointmentStatus), default=AppointmentStatus.planned)
    title: Mapped[str | None] = mapped_column(String(200))  # für Blockzeiten
    note: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    patient: Mapped[Patient | None] = relationship()
    therapist: Mapped[User] = relationship()
    prescription: Mapped[Prescription | None] = relationship()


class FollowUp(TimestampMixin, Base):
    """Wiedervorlage: Aufgabe/Erinnerung zu einem Patienten an einem Stichtag."""

    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_on: Mapped[date] = mapped_column(Date, index=True)
    text: Mapped[str] = mapped_column(String(500))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped[Patient] = relationship()
    created_by: Mapped[User] = relationship()


class Exercise(TimestampMixin, Base):
    """Übung der Übungsbibliothek."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), index=True)
    region: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    default_sets: Mapped[int | None] = mapped_column(Integer)
    default_reps: Mapped[int | None] = mapped_column(Integer)
    default_hold_seconds: Mapped[int | None] = mapped_column(Integer)
    contraindications: Mapped[str | None] = mapped_column(Text)  # "Nicht geeignet / Vorsicht bei …"
    # Mitgelieferte Beispielübungen sind ungeprüft, bis eine Fachperson sie freigibt. Nur freigegebene Übungen werden gedruckt.
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    image_path: Mapped[str | None] = mapped_column(String(300))
    image_content_type: Mapped[str | None] = mapped_column(String(64))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class ExercisePlan(TimestampMixin, VoidableMixin, Base):
    __tablename__ = "exercise_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    issued_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()
    items: Mapped[list["ExercisePlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="ExercisePlanItem.position"
    )


class ExercisePlanItem(Base):
    """Übung im Plan – Titel und Anleitung werden kopiert, damit spätere Bibliotheksänderungen ausgegebene Pläne nicht verändern."""

    __tablename__ = "exercise_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("exercise_plans.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(160))
    instructions: Mapped[str | None] = mapped_column(Text)
    sets: Mapped[int | None] = mapped_column(Integer)
    reps: Mapped[int | None] = mapped_column(Integer)
    hold_seconds: Mapped[int | None] = mapped_column(Integer)
    frequency: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[ExercisePlan] = relationship(back_populates="items")
    exercise: Mapped[Exercise | None] = relationship()


class ServiceItem(TimestampMixin, Base):
    """Leistungskatalog für Privat-/Selbstzahlerrechnungen. Preise in Cent."""

    __tablename__ = "service_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    price_cents: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Invoice(TimestampMixin, Base):
    """Rechnung. Entwürfe sind frei änderbar; gestellte Rechnungen sind unveränderlich (Korrektur nur per Stornorechnung)."""

    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("year", "seq", name="uq_invoice_year_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[InvoiceStatus] = mapped_column(_enum(InvoiceStatus), default=InvoiceStatus.draft, index=True)
    year: Mapped[int | None] = mapped_column(Integer)
    seq: Mapped[int | None] = mapped_column(Integer)
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    recipient_name: Mapped[str] = mapped_column(String(200))
    recipient_address: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    vat_note: Mapped[str | None] = mapped_column(Text)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    cancels_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))

    patient: Mapped[Patient] = relationship()
    created_by: Mapped[User] = relationship()
    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.position")
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice", cascade="all, delete-orphan", order_by="Payment.paid_on")

    @property
    def number(self) -> str | None:
        return f"{self.year}-{self.seq:04d}" if self.year and self.seq else None

    @property
    def paid_cents(self) -> int:
        return sum(p.amount_cents for p in self.payments if not p.voided)


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    treatment_id: Mapped[int | None] = mapped_column(ForeignKey("treatments.id"), index=True)
    service_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer)

    invoice: Mapped[Invoice] = relationship(back_populates="items")

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


class Payment(TimestampMixin, VoidableMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    paid_on: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(Integer)
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod), default=PaymentMethod.transfer)
    note: Mapped[str | None] = mapped_column(String(300))

    invoice: Mapped[Invoice] = relationship(back_populates="payments")
    created_by: Mapped[User] = relationship()


class IndicationEntry(TimestampMixin, Base):
    """Eintrag des Heilmittelkatalogs, von der Praxis nach dem aktuellen Katalog gepflegt (Mengenprüfung bei Verordnungen)."""

    __tablename__ = "indication_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(16), unique=True)  # Indikationsschlüssel
    name: Mapped[str] = mapped_column(String(200))
    max_units_per_rx: Mapped[int | None] = mapped_column(Integer)  # Höchstmenge je Verordnung
    orienting_total_units: Mapped[int | None] = mapped_column(Integer)  # orientierende Behandlungsmenge je Diagnose
    note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Examination(TimestampMixin, VoidableMixin, Base):
    """Erstbefund / Untersuchung: Inspektion, Palpation, Funktion, Hypothese und ICF-Einordnung."""

    __tablename__ = "examinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_on: Mapped[date] = mapped_column(Date)
    inspection: Mapped[str | None] = mapped_column(Text)
    palpation: Mapped[str | None] = mapped_column(Text)
    function: Mapped[str | None] = mapped_column(Text)  # Funktionsprüfung, Tests, Bewegungsanalyse
    hypothesis: Mapped[str | None] = mapped_column(Text)  # physiotherapeutische Hypothese / Beurteilung
    icf_body: Mapped[str | None] = mapped_column(Text)  # Körperfunktionen und -strukturen
    icf_activity: Mapped[str | None] = mapped_column(Text)  # Aktivitäten
    icf_participation: Mapped[str | None] = mapped_column(Text)  # Teilhabe
    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[User] = relationship()


class CatalogItem(TimestampMixin, Base):
    """Von der Praxis pflegbare Vorlagen: Warnzeichen, psychosoziale Faktoren, Maßnahmen, Befundvorlagen (inkl. Richtwerte).

    Die mitgelieferten Standardwerte werden beim ersten Zugriff angelegt und gelten als "ungeprüft", bis ein Administrator
    sie freigibt (reviewed). Einträge werden nie gelöscht, sondern deaktiviert (ältere Akten verweisen auf sie)."""

    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("kind", "key", name="uq_catalog_kind_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)  # red_flag | yellow_flag | measure | finding_preset
    key: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(16))  # nur Befundvorlagen: rom | strength | test | measure
    unit: Mapped[str | None] = mapped_column(String(16))
    norm_opposite: Mapped[float | None] = mapped_column(Float)  # Richtwerte Neutral-Null-Methode
    norm_neutral: Mapped[float | None] = mapped_column(Float)
    norm_main: Mapped[float | None] = mapped_column(Float)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))


class ClientOp(Base):
    """Protokoll übertragener Offline-Einträge: macht die Übertragung wiederholbar (Idempotenz) und löst vorläufige
    (negative) Kennungen von Tablets in echte auf."""

    __tablename__ = "client_ops"
    __table_args__ = (UniqueConstraint("user_id", "op_id", name="uq_client_op"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    op_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))
    temp_id: Mapped[int | None] = mapped_column(Integer, index=True)
    real_id: Mapped[int | None] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
