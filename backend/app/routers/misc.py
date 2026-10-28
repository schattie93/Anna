
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import catalog_service as cs
from ..catalog import TEST_RESULTS
from ..db import get_db
from ..deps import get_current_user
from ..models import Appointment, AppointmentStatus, AuditEntry, FollowUp, Patient, Prescription, Role, Treatment, TreatmentStatus, User
from ..prescription_rules import evaluate
from ..schemas import Catalog, Dashboard, FindingPreset, RxAttention, RxWarning
from ..timeutil import day_range_utc, local_today
from .scheduling import _follow_up_out, appointment_out

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/catalog", response_model=Catalog)
def catalog(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    def norm(i):
        return (i.norm_opposite, i.norm_neutral, i.norm_main) if None not in (i.norm_opposite, i.norm_neutral, i.norm_main) else None

    all_red, all_yellow = cs.items(db, "red_flag", False), cs.items(db, "yellow_flag", False)
    return Catalog(
        red_flags={i.key: i.label for i in all_red if i.active},
        red_flags_all={i.key: i.label for i in all_red},
        yellow_flags={i.key: i.label for i in all_yellow if i.active},
        yellow_flags_all={i.key: i.label for i in all_yellow},
        measures=[i.label for i in cs.items(db, "measure")],
        finding_presets=[
            FindingPreset(category=i.category or "measure", name=i.label, unit=i.unit, norm=norm(i), reviewed=i.reviewed)
            for i in cs.items(db, "finding_preset")
        ],
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
