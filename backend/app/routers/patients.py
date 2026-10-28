from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import get_current_user, get_patient
from ..models import AuditEntry, Patient, User
from ..schemas import AuditOut, PatientCreate, PatientListItem, PatientOut, PatientUpdate

router = APIRouter(prefix="/api/patients", tags=["patients"])


def _next_patient_number(db: Session) -> str:
    last = db.scalar(select(func.max(Patient.id))) or 0
    return f"P{last + 1:05d}"


@router.get("", response_model=list[PatientListItem])
def search_patients(
    q: str = "",
    include_archived: bool = False,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Patient)
    for term in q.split():
        like = f"%{term.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Patient.first_name).like(like),
                func.lower(Patient.last_name).like(like),
                func.lower(Patient.patient_number).like(like),
                func.lower(Patient.city).like(like),
            )
        )
    if not include_archived:
        stmt = stmt.where(Patient.archived.is_(False))
    return db.scalars(stmt.order_by(Patient.last_name, Patient.first_name).limit(limit)).all()


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(data: PatientCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    patient = Patient(**data.model_dump(), patient_number=_next_patient_number(db))
    db.add(patient)
    db.flush()
    audit.log(db, user, "create", "patient", patient.id, patient.id, changes=audit.snapshot(patient, list(type(data).model_fields)))
    db.commit()
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def read_patient(patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    audit.log(db, user, "view", "patient", patient.id, patient.id)
    db.commit()
    return patient


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(
    data: PatientUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    diff = audit.apply_changes(patient, data.model_dump())
    if diff:
        audit.log(db, user, "update", "patient", patient.id, patient.id, changes=diff)
    db.commit()
    return patient


@router.get("/{patient_id}/history", response_model=list[AuditOut])
def patient_history(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return db.scalars(
        select(AuditEntry)
        .where(AuditEntry.patient_id == patient.id, AuditEntry.action != "view")
        .order_by(AuditEntry.at.desc(), AuditEntry.id.desc())
    ).all()
