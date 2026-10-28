
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..catalog import FINDING_PRESETS, MEASURES, RED_FLAGS, ROM_NORMS, TEST_RESULTS, YELLOW_FLAGS
from ..db import get_db
from ..deps import get_current_user
from ..models import Appointment, AppointmentStatus, AuditEntry, FollowUp, Patient, Prescription, Role, Treatment, TreatmentStatus, User
from ..prescription_rules import evaluate
from ..schemas import Catalog, Dashboard, FindingPreset, RxAttention, RxWarning
from ..timeutil import day_range_utc, local_today
from .scheduling import _follow_up_out, appointment_out

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/catalog", response_model=Catalog)
def catalog(_: User = Depends(get_current_user)):
    return Catalog(
        red_flags=RED_FLAGS,
        yellow_flags=YELLOW_FLAGS,
        rom_norms=ROM_NORMS,
        measures=MEASURES,
        finding_presets=[FindingPreset(category=c, name=n, unit=u) for c, n, u in FINDING_PRESETS],
        test_results=TEST_RESULTS,
    )


@router.get("/dashboard", response_model=Dashboard)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    active = Treatment.voided.is_(False)
    open_treatments: list[Treatment] = []
    if user.role != Role.reception:
        open_treatments = list(
            db.scalars(
                select(Treatment)
                .options(selectinload(Treatment.patient))
                .where(active, Treatment.status == TreatmentStatus.draft)
                .order_by(Treatment.treated_on)
                .limit(50)
            )
        )

    # Zuletzt vom angemeldeten Benutzer geöffnete oder bearbeitete Patienten
    recent_ids = db.execute(
        select(AuditEntry.patient_id, func.max(AuditEntry.at).label("last"))
        .where(AuditEntry.user_id == user.id, AuditEntry.patient_id.is_not(None))
        .group_by(AuditEntry.patient_id)
        .order_by(func.max(AuditEntry.at).desc())
        .limit(8)
    ).all()
    patients = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_([r[0] for r in recent_ids])))}

    today = local_today()
    lo, hi = day_range_utc(today)
    appointments = db.scalars(
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.therapist), selectinload(Appointment.prescription))
        .where(Appointment.start >= lo, Appointment.start < hi, Appointment.status != AppointmentStatus.cancelled)
        .order_by(Appointment.start)
    )
    follow_ups = db.scalars(
        select(FollowUp)
        .options(selectinload(FollowUp.patient), selectinload(FollowUp.created_by))
        .where(FollowUp.done.is_(False), FollowUp.due_on <= today)
        .order_by(FollowUp.due_on)
        .limit(30)
    )
    attention: list[RxAttention] = []
    if user.role != Role.reception:
        for rx in db.scalars(select(Prescription).options(selectinload(Prescription.created_by)).where(Prescription.voided.is_(False))):
            treatments = list(db.scalars(select(Treatment).where(Treatment.patient_id == rx.patient_id)))
            info = evaluate(rx, treatments, today, db)
            if info["status"] == "open" and info["warnings"]:
                patient = db.get(Patient, rx.patient_id)
                attention.append(
                    RxAttention(
                        patient=patient, prescription_id=rx.id, measure=rx.measure, units_done=info["units_done"],
                        total_units=rx.total_units, warnings=[RxWarning(**w) for w in info["warnings"]],
                    )
                )

    return Dashboard(
        appointments_today=[appointment_out(db, a) for a in appointments],
        follow_ups_due=[_follow_up_out(f) for f in follow_ups],
        rx_attention=attention,
        patient_count=db.scalar(select(func.count(Patient.id)).where(Patient.archived.is_(False))),
        treatments_today=db.scalar(select(func.count(Treatment.id)).where(active, Treatment.treated_on == local_today())),
        open_treatments=open_treatments,
        recent_patients=[patients[r[0]] for r in recent_ids if r[0] in patients],
    )
