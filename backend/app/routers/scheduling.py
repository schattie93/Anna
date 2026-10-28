"""Termine (Kalender, Serien, Blockzeiten, Absagen), Erinnerungen und Wiedervorlagen."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import audit
from ..db import get_db
from ..deps import get_current_user, get_patient, require_medical
from ..models import (
    Appointment,
    AppointmentStatus,
    FollowUp,
    Patient,
    Prescription,
    Role,
    Treatment,
    User,
)
from ..prescription_rules import evaluate
from ..schemas import (
    AppointmentCreated,
    AppointmentIn,
    AppointmentOut,
    AppointmentUpdate,
    FollowUpIn,
    FollowUpOut,
    ReminderOut,
    SkippedAppointment,
    TreatmentOut,
)
from ..timeutil import as_utc, day_range_utc, local_today, to_utc, tz

router = APIRouter(prefix="/api", tags=["scheduling"])

BUSY = (AppointmentStatus.planned, AppointmentStatus.done)


def appointment_out(db: Session, a: Appointment) -> AppointmentOut:
    out = AppointmentOut.model_validate(a)
    out.start, out.end = as_utc(a.start), as_utc(a.end)
    if a.prescription and not a.prescription.voided:
        treatments = list(db.scalars(select(Treatment).where(Treatment.patient_id == a.prescription.patient_id)))
        info = evaluate(a.prescription, treatments)
        out.prescription_label = f"{a.prescription.measure} {info['units_done']}/{a.prescription.total_units}"
    return out


def _conflicts(db: Session, therapist_id: int, start: datetime, end: datetime, exclude_id: int | None = None) -> Appointment | None:
    stmt = select(Appointment).where(
        Appointment.therapist_id == therapist_id, Appointment.status.in_(BUSY), Appointment.start < end, Appointment.end > start
    )
    if exclude_id:
        stmt = stmt.where(Appointment.id != exclude_id)
    return db.scalars(stmt.limit(1)).first()


def _check_prescription(db: Session, patient_id: int | None, prescription_id: int | None) -> None:
    if prescription_id is None:
        return
    rx = db.get(Prescription, prescription_id)
    if not rx or rx.patient_id != patient_id or rx.voided:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Verordnung gehört nicht zu diesem Patienten")


def _conflict_text(c: Appointment) -> str:
    who = f"{c.patient.last_name}, {c.patient.first_name}" if c.patient else (c.title or "Blockzeit")
    return f"Überschneidung mit Termin {as_utc(c.start).astimezone(tz()).strftime('%H:%M')} ({who})"


def _load(db: Session, appointment_id: int) -> Appointment:
    a = db.get(Appointment, appointment_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Termin nicht gefunden")
    return a


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    start: datetime,
    end: datetime,
    therapist_id: int | None = None,
    patient_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.therapist), selectinload(Appointment.prescription))
        .where(Appointment.start >= to_utc(start), Appointment.start < to_utc(end))
        .order_by(Appointment.start)
    )
    if therapist_id:
        stmt = stmt.where(Appointment.therapist_id == therapist_id)
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    return [appointment_out(db, a) for a in db.scalars(stmt)]


@router.post("/appointments", response_model=AppointmentCreated, status_code=status.HTTP_201_CREATED)
def create_appointments(data: AppointmentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.patient_id is not None and not db.get(Patient, data.patient_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient nicht gefunden")
    _check_prescription(db, data.patient_id, data.prescription_id)
    therapist = db.get(User, data.therapist_id) if data.therapist_id else user
    if not therapist or not therapist.is_active or therapist.role == Role.reception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ungültige Therapeutin / ungültiger Therapeut")

    first_start = to_utc(data.start)
    created: list[Appointment] = []
    skipped: list[SkippedAppointment] = []
    for i in range(data.repeat_count):
        start = first_start + timedelta(days=i * data.repeat_days)
        end = start + timedelta(minutes=data.duration_minutes)
        clash = None if data.force else _conflicts(db, therapist.id, start, end)
        if clash:
            if data.repeat_count == 1:
                raise HTTPException(status.HTTP_409_CONFLICT, _conflict_text(clash))
            skipped.append(SkippedAppointment(start=start, reason=_conflict_text(clash)))
            continue
        a = Appointment(
            patient_id=data.patient_id, therapist_id=therapist.id, prescription_id=data.prescription_id, start=start, end=end,
            title=(data.title or "").strip() or None, note=data.note,
        )
        db.add(a)
        db.flush()
        audit.log(db, user, "create", "appointment", a.id, a.patient_id, changes={"start": start.isoformat(), "end": end.isoformat()})
        created.append(a)
    db.commit()
    for a in created:
        db.refresh(a)
    return AppointmentCreated(created=[appointment_out(db, a) for a in created], skipped=skipped)


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: int, data: AppointmentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = _load(db, appointment_id)
    fields = data.model_dump(exclude_unset=True, exclude={"force", "duration_minutes", "start"})
    if "prescription_id" in fields:
        _check_prescription(db, a.patient_id, fields["prescription_id"])
    new_status = fields.get("status", a.status)
    if new_status in (AppointmentStatus.cancelled, AppointmentStatus.no_show) and a.status == AppointmentStatus.planned and not (fields.get("cancel_reason") or a.cancel_reason):
        fields["cancel_reason"] = "ohne Angabe"
    diff = audit.apply_changes(a, fields)
    if data.start is not None or data.duration_minutes is not None:
        start = to_utc(data.start) if data.start else as_utc(a.start)
        minutes = data.duration_minutes or int((as_utc(a.end) - as_utc(a.start)).total_seconds() // 60)
        end = start + timedelta(minutes=minutes)
        if new_status in BUSY and not data.force:
            clash = _conflicts(db, a.therapist_id, start, end, exclude_id=a.id)
            if clash:
                raise HTTPException(status.HTTP_409_CONFLICT, _conflict_text(clash))
        diff.update(audit.apply_changes(a, {"start": start, "end": end}))
    if diff:
        audit.log(db, user, "update", "appointment", a.id, a.patient_id, changes=diff)
    db.commit()
    return appointment_out(db, a)


class StartIn(BaseModel):
    treated_on: date


@router.post("/appointments/{appointment_id}/start", response_model=TreatmentOut, dependencies=[Depends(require_medical)])
def start_treatment(appointment_id: int, data: StartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Legt aus dem Termin einen Behandlungsentwurf an und markiert den Termin als durchgeführt."""
    a = _load(db, appointment_id)
    if a.patient_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Blockzeiten haben keine Behandlung")
    if a.treatment_id:
        return db.get(Treatment, a.treatment_id)
    t = Treatment(
        patient_id=a.patient_id, created_by_id=user.id, treated_on=data.treated_on, prescription_id=a.prescription_id,
        duration_minutes=int((as_utc(a.end) - as_utc(a.start)).total_seconds() // 60),
    )
    db.add(t)
    db.flush()
    a.treatment_id = t.id
    a.status = AppointmentStatus.done
    audit.log(db, user, "create", "treatment", t.id, a.patient_id, changes={"from_appointment": a.id})
    db.commit()
    return t


@router.get("/appointments/reminders", response_model=list[ReminderOut])
def reminders(day: date | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Termine eines Tages (Standard: morgen) mit Telefonnummern – für Erinnerungsanrufe oder einen Ausdruck."""
    day = day or local_today() + timedelta(days=1)
    lo, hi = day_range_utc(day)
    rows = db.scalars(
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.therapist), selectinload(Appointment.prescription))
        .where(Appointment.start >= lo, Appointment.start < hi, Appointment.status == AppointmentStatus.planned, Appointment.patient_id.is_not(None))
        .order_by(Appointment.start)
    )
    return [ReminderOut(appointment=appointment_out(db, a), phone=a.patient.phone, mobile=a.patient.mobile) for a in rows]


# --- Wiedervorlagen ------------------------------------------------------------


def _follow_up_out(f: FollowUp) -> FollowUpOut:
    return FollowUpOut.model_validate(f)


@router.get("/follow-ups", response_model=list[FollowUpOut])
def list_follow_ups(
    until: date | None = None,
    include_done: bool = False,
    patient_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(FollowUp).options(selectinload(FollowUp.patient), selectinload(FollowUp.created_by)).order_by(FollowUp.due_on, FollowUp.id)
    if not include_done:
        stmt = stmt.where(FollowUp.done.is_(False))
    if until:
        stmt = stmt.where(FollowUp.due_on <= until)
    if patient_id:
        stmt = stmt.where(FollowUp.patient_id == patient_id)
    return [_follow_up_out(f) for f in db.scalars(stmt)]


@router.post("/patients/{patient_id}/follow-ups", response_model=FollowUpOut, status_code=status.HTTP_201_CREATED)
def create_follow_up(data: FollowUpIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = FollowUp(patient_id=patient.id, created_by_id=user.id, due_on=data.due_on, text=data.text)
    db.add(f)
    db.flush()
    audit.log(db, user, "create", "follow_up", f.id, patient.id, changes={"due_on": data.due_on.isoformat()})
    db.commit()
    db.refresh(f)
    return _follow_up_out(f)


class DoneIn(BaseModel):
    done: bool = True


@router.patch("/follow-ups/{follow_up_id}", response_model=FollowUpOut)
def mark_follow_up(follow_up_id: int, data: DoneIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    f = db.get(FollowUp, follow_up_id)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wiedervorlage nicht gefunden")
    f.done = data.done
    f.done_at = datetime.now(timezone.utc) if data.done else None
    audit.log(db, user, "update", "follow_up", f.id, f.patient_id, changes={"done": {"old": not data.done, "new": data.done}})
    db.commit()
    return _follow_up_out(f)
