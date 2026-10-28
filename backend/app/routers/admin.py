"""Verwaltung: Änderungsprotokoll, Betriebsstatus, Integritätsprüfung, Aufbewahrung/Löschung und Akten-Export."""

import json
import os
import tempfile
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.background import BackgroundTask

from .. import audit, ops, storage
from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user, get_patient, require_admin, require_medical
from ..models import AuditEntry, Patient, User
from ..schemas import AuditOut, PatientListItem

router = APIRouter(prefix="/api", tags=["admin"])


class AdminAudit(AuditOut):
    patient: PatientListItem | None = None


@router.get("/admin/audit", response_model=list[AdminAudit], dependencies=[Depends(require_admin)])
def audit_log(
    action: str | None = None,
    entity_type: str | None = None,
    user_id: int | None = None,
    patient_id: int | None = None,
    include_views: bool = False,
    before_id: int | None = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(AuditEntry).options(selectinload(AuditEntry.user)).order_by(AuditEntry.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditEntry.action == action)
    elif not include_views:
        stmt = stmt.where(AuditEntry.action != "view")
    if entity_type:
        stmt = stmt.where(AuditEntry.entity_type == entity_type)
    if user_id:
        stmt = stmt.where(AuditEntry.user_id == user_id)
    if patient_id:
        stmt = stmt.where(AuditEntry.patient_id == patient_id)
    if before_id:
        stmt = stmt.where(AuditEntry.id < before_id)
    rows = db.scalars(stmt).all()
    patients = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_({r.patient_id for r in rows if r.patient_id})))}
    out = []
    for r in rows:
        item = AdminAudit.model_validate(r)
        item.patient = PatientListItem.model_validate(patients[r.patient_id]) if r.patient_id in patients else None
        out.append(item)
    return out


@router.get("/admin/ops", dependencies=[Depends(require_admin)])
def ops_status(db: Session = Depends(get_db)):
    s = get_settings()
    return {**ops.get_ops(db), "idle_minutes": s.idle_minutes, "retention_years": s.retention_years, "cookie_secure": s.cookie_secure}


@router.get("/admin/integrity", dependencies=[Depends(require_admin)])
def integrity(db: Session = Depends(get_db)):
    return ops.check_integrity(db)


class RetentionRow(BaseModel):
    patient: PatientListItem
    last_activity: date
    retention_until: date
    eligible: bool


@router.get("/admin/retention", response_model=list[RetentionRow], dependencies=[Depends(require_admin)])
def retention(only_eligible: bool = False, db: Session = Depends(get_db)):
    rows = ops.retention_candidates(db)
    return [RetentionRow(**r) for r in rows if r["eligible"] or not only_eligible]


class EraseIn(BaseModel):
    confirm_number: str
    reason: str


@router.post("/admin/patients/{patient_id}/erase")
def erase(patient_id: int, data: EraseIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Unwiderrufliches Löschen. Die Patientennummer muss zur Bestätigung eingegeben werden; vor Ablauf der Aufbewahrungsfrist
    ist eine Begründung Pflicht (z. B. Löschverlangen nach Art. 17 DSGVO nach rechtlicher Prüfung)."""
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient nicht gefunden")
    if data.confirm_number.strip() != patient.patient_number:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Patientennummer stimmt nicht überein")
    if not data.reason.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Begründung fehlt")
    result = ops.erase_patient(db, patient, admin, data.reason.strip())
    db.commit()
    return result


@router.get("/patients/{patient_id}/export.zip", dependencies=[Depends(require_medical)])
def export_record(patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Vollständige Patientenakte (JSON + Dateien) für Auskunft/Übertragbarkeit nach Art. 15/20 DSGVO."""
    data, attachments = ops.export_record(db, patient)
    fd, tmp = tempfile.mkstemp(suffix=".zip", prefix="physioflow-export-")
    os.close(fd)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("akte.json", json.dumps(data, ensure_ascii=False, indent=2))
        z.writestr(
            "LIESMICH.txt",
            "PhysioFlow – Export einer Patientenakte\n\nakte.json enthält alle gespeicherten Daten, der Ordner dateien/ Fotos, Dokumente und Zeichnungen.\n"
            "Stornierte Einträge sind mit voided=true gekennzeichnet und bleiben zur Nachvollziehbarkeit enthalten.\n",
        )
        for a in attachments:
            path = storage.resolve(a.path)
            if path.is_file():
                z.write(path, f"dateien/{a.id}_{path.name}")
    audit.log(db, user, "export", "record", None, patient.id)
    db.commit()
    return FileResponse(
        tmp, media_type="application/zip", filename=f"akte-{patient.patient_number}.zip",
        headers={"Cache-Control": "no-store"}, background=BackgroundTask(os.unlink, tmp),
    )
