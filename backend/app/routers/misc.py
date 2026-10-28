from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..catalog import MEASURES, RED_FLAGS
from ..db import get_db
from ..deps import get_current_user
from ..models import AuditEntry, Patient, Treatment, TreatmentStatus, User
from ..schemas import Catalog, Dashboard

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/catalog", response_model=Catalog)
def catalog(_: User = Depends(get_current_user)):
    return Catalog(red_flags=RED_FLAGS, measures=MEASURES)


@router.get("/dashboard", response_model=Dashboard)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    active = Treatment.voided.is_(False)
    open_treatments = db.scalars(
        select(Treatment)
        .options(selectinload(Treatment.patient))
        .where(active, Treatment.status == TreatmentStatus.draft)
        .order_by(Treatment.treated_on)
        .limit(50)
    ).all()

    # Zuletzt vom angemeldeten Benutzer geöffnete oder bearbeitete Patienten
    recent_ids = db.execute(
        select(AuditEntry.patient_id, func.max(AuditEntry.at).label("last"))
        .where(AuditEntry.user_id == user.id, AuditEntry.patient_id.is_not(None))
        .group_by(AuditEntry.patient_id)
        .order_by(func.max(AuditEntry.at).desc())
        .limit(8)
    ).all()
    patients = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_([r[0] for r in recent_ids])))}

    return Dashboard(
        patient_count=db.scalar(select(func.count(Patient.id)).where(Patient.archived.is_(False))),
        treatments_today=db.scalar(select(func.count(Treatment.id)).where(active, Treatment.treated_on == date.today())),
        open_treatments=open_treatments,
        recent_patients=[patients[r[0]] for r in recent_ids if r[0] in patients],
    )
