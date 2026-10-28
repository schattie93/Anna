"""Anamnesen, Diagnosen und Behandlungen.

Regeln: Einträge werden nie gelöscht, nur storniert. Korrekturen an Anamnesen und an
abgeschlossenen Behandlungen erfordern eine Begründung; jede Änderung landet im Protokoll.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import get_current_user, get_patient, require_medical
from ..models import Anamnesis, Diagnosis, Patient, Treatment, TreatmentStatus, User
from ..schemas import (
    AnamnesisIn,
    AnamnesisOut,
    AnamnesisUpdate,
    DiagnosisIn,
    DiagnosisOut,
    DiagnosisUpdate,
    TreatmentIn,
    TreatmentOut,
    TreatmentUpdate,
    VoidIn,
)

router = APIRouter(prefix="/api/patients/{patient_id}", tags=["medical"], dependencies=[Depends(require_medical)])


def _get_entry(db: Session, model, entry_id: int, patient: Patient):
    entry = db.get(model, entry_id)
    if not entry or entry.patient_id != patient.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Eintrag nicht gefunden")
    return entry


def _ensure_not_voided(entry) -> None:
    if entry.voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stornierte Einträge können nicht geändert werden")


def _void(db: Session, entry, entity: str, reason: str, user: User):
    _ensure_not_voided(entry)
    entry.voided = True
    entry.void_reason = reason
    entry.voided_at = datetime.now(timezone.utc)
    audit.log(db, user, "void", entity, entry.id, entry.patient_id, reason=reason)
    db.commit()
    return entry


def _list(db: Session, model, patient: Patient, *order):
    return db.scalars(select(model).where(model.patient_id == patient.id).order_by(*order)).all()


# --- Anamnese ----------------------------------------------------------------


@router.get("/anamneses", response_model=list[AnamnesisOut])
def list_anamneses(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return _list(db, Anamnesis, patient, Anamnesis.recorded_on.desc(), Anamnesis.id.desc())


@router.post("/anamneses", response_model=AnamnesisOut, status_code=status.HTTP_201_CREATED)
def create_anamnesis(
    data: AnamnesisIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    entry = Anamnesis(**data.model_dump(), patient_id=patient.id, created_by_id=user.id)
    db.add(entry)
    db.flush()
    audit.log(db, user, "create", "anamnesis", entry.id, patient.id, changes=audit.snapshot(entry, list(type(data).model_fields)))
    db.commit()
    return entry


@router.put("/anamneses/{entry_id}", response_model=AnamnesisOut)
def update_anamnesis(
    entry_id: int,
    data: AnamnesisUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = _get_entry(db, Anamnesis, entry_id, patient)
    _ensure_not_voided(entry)
    diff = audit.apply_changes(entry, data.model_dump(exclude={"correction_reason"}))
    if diff:
        audit.log(db, user, "correct", "anamnesis", entry.id, patient.id, changes=diff, reason=data.correction_reason)
    db.commit()
    return entry


@router.post("/anamneses/{entry_id}/void", response_model=AnamnesisOut)
def void_anamnesis(
    entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _void(db, _get_entry(db, Anamnesis, entry_id, patient), "anamnesis", data.reason, user)


# --- Diagnosen ---------------------------------------------------------------


def _clear_other_primary(db: Session, patient: Patient, keep_id: int) -> None:
    db.execute(
        update(Diagnosis)
        .where(Diagnosis.patient_id == patient.id, Diagnosis.id != keep_id, Diagnosis.is_primary.is_(True))
        .values(is_primary=False)
    )


@router.get("/diagnoses", response_model=list[DiagnosisOut])
def list_diagnoses(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return _list(db, Diagnosis, patient, Diagnosis.is_primary.desc(), Diagnosis.created_at.desc())


@router.post("/diagnoses", response_model=DiagnosisOut, status_code=status.HTTP_201_CREATED)
def create_diagnosis(
    data: DiagnosisIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    entry = Diagnosis(**data.model_dump(), patient_id=patient.id, created_by_id=user.id)
    db.add(entry)
    db.flush()
    if entry.is_primary:
        _clear_other_primary(db, patient, entry.id)
    audit.log(db, user, "create", "diagnosis", entry.id, patient.id, changes=audit.snapshot(entry, list(type(data).model_fields)))
    db.commit()
    return entry


@router.put("/diagnoses/{entry_id}", response_model=DiagnosisOut)
def update_diagnosis(
    entry_id: int,
    data: DiagnosisUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = _get_entry(db, Diagnosis, entry_id, patient)
    _ensure_not_voided(entry)
    diff = audit.apply_changes(entry, data.model_dump(exclude={"correction_reason"}))
    if entry.is_primary:
        _clear_other_primary(db, patient, entry.id)
    if diff:
        audit.log(db, user, "update", "diagnosis", entry.id, patient.id, changes=diff, reason=data.correction_reason)
    db.commit()
    return entry


@router.post("/diagnoses/{entry_id}/void", response_model=DiagnosisOut)
def void_diagnosis(
    entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _void(db, _get_entry(db, Diagnosis, entry_id, patient), "diagnosis", data.reason, user)


# --- Behandlungen ------------------------------------------------------------


def _check_diagnosis(db: Session, patient: Patient, diagnosis_id: int | None) -> None:
    if diagnosis_id is None:
        return
    diagnosis = db.get(Diagnosis, diagnosis_id)
    if not diagnosis or diagnosis.patient_id != patient.id or diagnosis.voided:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Diagnose gehört nicht zu diesem Patienten")


@router.get("/treatments", response_model=list[TreatmentOut])
def list_treatments(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return _list(db, Treatment, patient, Treatment.treated_on.desc(), Treatment.id.desc())


@router.post("/treatments", response_model=TreatmentOut, status_code=status.HTTP_201_CREATED)
def create_treatment(
    data: TreatmentIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    _check_diagnosis(db, patient, data.diagnosis_id)
    entry = Treatment(**data.model_dump(exclude={"finalize"}), patient_id=patient.id, created_by_id=user.id)
    if data.finalize:
        entry.status = TreatmentStatus.final
        entry.finalized_at = datetime.now(timezone.utc)
    db.add(entry)
    db.flush()
    changes = audit.snapshot(entry, [*TreatmentIn.model_fields.keys() - {"finalize"}, "status"])
    audit.log(db, user, "create", "treatment", entry.id, patient.id, changes=changes)
    db.commit()
    return entry


@router.put("/treatments/{entry_id}", response_model=TreatmentOut)
def update_treatment(
    entry_id: int,
    data: TreatmentUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = _get_entry(db, Treatment, entry_id, patient)
    _ensure_not_voided(entry)
    _check_diagnosis(db, patient, data.diagnosis_id)
    was_final = entry.status == TreatmentStatus.final
    reason = (data.correction_reason or "").strip() or None
    if was_final and not reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Korrektur einer abgeschlossenen Behandlung erfordert eine Begründung")

    diff = audit.apply_changes(entry, data.model_dump(exclude={"finalize", "correction_reason"}))
    if data.finalize and not was_final:
        entry.status = TreatmentStatus.final
        entry.finalized_at = datetime.now(timezone.utc)
        diff["status"] = {"old": TreatmentStatus.draft.value, "new": TreatmentStatus.final.value}
    if diff:
        action = "correct" if was_final else "update"
        audit.log(db, user, action, "treatment", entry.id, patient.id, changes=diff, reason=reason)
    db.commit()
    return entry


@router.post("/treatments/{entry_id}/void", response_model=TreatmentOut)
def void_treatment(
    entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _void(db, _get_entry(db, Treatment, entry_id, patient), "treatment", data.reason, user)
