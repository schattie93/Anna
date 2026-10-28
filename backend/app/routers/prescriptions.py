"""Heilmittelverordnungen mit Prüfhinweisen."""

from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import get_current_user, get_patient, require_medical
from ..models import Patient, Prescription, Treatment, User
from ..prescription_rules import evaluate
from ..schemas import PrescriptionIn, PrescriptionOut, PrescriptionUpdate, RxWarning, VoidIn
from .medical import _ensure_not_voided, _get_entry, _void

router = APIRouter(prefix="/api/patients/{patient_id}/prescriptions", tags=["prescriptions"], dependencies=[Depends(require_medical)])


def rx_out(rx: Prescription, treatments: list[Treatment], today: date | None = None) -> PrescriptionOut:
    out = PrescriptionOut.model_validate(rx)
    info = evaluate(rx, treatments, today)
    out.units_done, out.units_remaining = info["units_done"], info["units_remaining"]
    out.status, out.latest_start = info["status"], info["latest_start"]
    out.warnings = [RxWarning(**w) for w in info["warnings"]]
    return out


def patient_treatments(db: Session, patient_id: int) -> list[Treatment]:
    return list(db.scalars(select(Treatment).where(Treatment.patient_id == patient_id)))


@router.get("", response_model=list[PrescriptionOut])
def list_prescriptions(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    treatments = patient_treatments(db, patient.id)
    rows = db.scalars(select(Prescription).where(Prescription.patient_id == patient.id).order_by(Prescription.issued_on.desc(), Prescription.id.desc()))
    return [rx_out(rx, treatments) for rx in rows]


@router.post("", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
def create_prescription(data: PrescriptionIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rx = Prescription(**data.model_dump(), patient_id=patient.id, created_by_id=user.id)
    db.add(rx)
    db.flush()
    audit.log(db, user, "create", "prescription", rx.id, patient.id, changes=audit.snapshot(rx, list(PrescriptionIn.model_fields)))
    db.commit()
    return rx_out(rx, patient_treatments(db, patient.id))


@router.put("/{entry_id}", response_model=PrescriptionOut)
def update_prescription(
    entry_id: int,
    data: PrescriptionUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rx = _get_entry(db, Prescription, entry_id, patient)
    _ensure_not_voided(rx)
    diff = audit.apply_changes(rx, data.model_dump(exclude={"correction_reason"}))
    if diff:
        audit.log(db, user, "update", "prescription", rx.id, patient.id, changes=diff, reason=data.correction_reason)
    db.commit()
    return rx_out(rx, patient_treatments(db, patient.id))


@router.post("/{entry_id}/void", response_model=PrescriptionOut)
def void_prescription(entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rx = _void(db, _get_entry(db, Prescription, entry_id, patient), "prescription", data.reason, user)
    return rx_out(rx, patient_treatments(db, patient.id))
