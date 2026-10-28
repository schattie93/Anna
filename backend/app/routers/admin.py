"""Verwaltung: Änderungsprotokoll, Betriebsstatus, Integritätsprüfung, Aufbewahrung/Löschung und Akten-Export."""

import json
import os
import tempfile
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
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
    from .. import catalog_service as cs
    from ..models import CatalogItem

    cs.ensure_seeded(db)
    unreviewed = db.scalar(select(func.count(CatalogItem.id)).where(CatalogItem.reviewed.is_(False), CatalogItem.active.is_(True)))
    return {**ops.get_ops(db), "unreviewed_templates": unreviewed, "idle_minutes": s.idle_minutes, "retention_years": s.retention_years, "cookie_secure": s.cookie_secure}


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


# --- Vorlagen (Warnzeichen, psychosoziale Faktoren, Maßnahmen, Befundvorlagen) ----------------

from .. import catalog_service as cs  # noqa: E402
from ..models import CatalogItem  # noqa: E402
from ..schemas import CatalogItemIn, CatalogItemOut, CatalogItemUpdate  # noqa: E402


def _check_item(kind: str, category: str | None) -> None:
    if kind not in cs.KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unbekannte Vorlagenart")
    if kind == "finding_preset" and category not in cs.CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Befundvorlagen brauchen eine Kategorie (Beweglichkeit, Kraft, Test, Messwert)")


def _snapshot(item: CatalogItem) -> dict:
    return {f: getattr(item, f) for f in ("label", "category", "unit", "norm_opposite", "norm_neutral", "norm_main", "active", "reviewed")}


@router.get("/admin/catalog", response_model=list[CatalogItemOut], dependencies=[Depends(require_admin)])
def list_catalog(kind: str, db: Session = Depends(get_db)):
    if kind not in cs.KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unbekannte Vorlagenart")
    return cs.items(db, kind, only_active=False)


@router.post("/admin/catalog", response_model=CatalogItemOut, status_code=status.HTTP_201_CREATED)
def create_catalog_item(data: CatalogItemIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _check_item(data.kind, data.category)
    last = max((i.sort_order for i in cs.items(db, data.kind, only_active=False)), default=0)
    item = CatalogItem(
        kind=data.kind, key=cs.unique_key(db, data.kind, data.label), label=data.label.strip(), sort_order=last + 10, active=True,
        category=data.category if data.kind == "finding_preset" else None, unit=data.unit or None,
        norm_opposite=data.norm_opposite, norm_neutral=data.norm_neutral, norm_main=data.norm_main,
        reviewed=True, reviewed_by=admin.full_name,  # selbst angelegte Vorlagen stammen von der Praxis
    )
    db.add(item)
    db.flush()
    audit.log(db, admin, "create", "catalog", item.id, changes={"kind": item.kind, "label": item.label})
    db.commit()
    return item


@router.put("/admin/catalog/{item_id}", response_model=CatalogItemOut)
def update_catalog_item(item_id: int, data: CatalogItemUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    item = db.get(CatalogItem, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorlage nicht gefunden")
    _check_item(item.kind, data.category if item.kind == "finding_preset" else None)
    values = data.model_dump()
    if item.kind != "finding_preset":
        values["category"] = None
    # Der Schlüssel (key) bleibt stabil; geändert wird nur der angezeigte Text.
    diff = audit.apply_changes(item, {**values, "label": data.label.strip(), "unit": data.unit or None})
    if data.reviewed and not _was_reviewed(diff):
        item.reviewed_by = admin.full_name
    if diff:
        audit.log(db, admin, "update", "catalog", item.id, changes=diff)
    db.commit()
    return item


def _was_reviewed(diff: dict) -> bool:
    return "reviewed" not in diff  # unverändert bereits geprüft


class MoveIn(BaseModel):
    direction: str  # up | down


@router.post("/admin/catalog/{item_id}/move", response_model=list[CatalogItemOut])
def move_catalog_item(item_id: int, data: MoveIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    item = db.get(CatalogItem, item_id)
    if not item or data.direction not in ("up", "down"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorlage nicht gefunden")
    siblings = cs.items(db, item.kind, only_active=False)
    idx = next(i for i, x in enumerate(siblings) if x.id == item.id)
    other = idx - 1 if data.direction == "up" else idx + 1
    if 0 <= other < len(siblings):
        siblings[idx], siblings[other] = siblings[other], siblings[idx]
        for n, x in enumerate(siblings):
            x.sort_order = (n + 1) * 10
        audit.log(db, admin, "update", "catalog", item.id, changes={"sort_order": {"old": idx, "new": other}})
        db.commit()
    return siblings


class ReviewIn(BaseModel):
    kind: str | None = None


@router.post("/admin/catalog/review-all")
def review_all(data: ReviewIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Markiert alle (aktiven) Vorlagen der Art als von der Praxis geprüft."""
    cs.ensure_seeded(db)
    stmt = select(CatalogItem).where(CatalogItem.reviewed.is_(False), CatalogItem.active.is_(True))
    if data.kind:
        stmt = stmt.where(CatalogItem.kind == data.kind)
    rows = db.scalars(stmt).all()
    for i in rows:
        i.reviewed, i.reviewed_by = True, admin.full_name
    audit.log(db, admin, "update", "catalog", changes={"reviewed_all": len(rows), "kind": data.kind})
    db.commit()
    return {"reviewed": len(rows)}
