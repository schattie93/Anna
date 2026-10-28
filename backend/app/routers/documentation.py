"""Phase 2: Befunde, Körperatlas, Dateien (Fotos, Dokumente, Zeichnungen), Therapieziele."""

from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, storage
from ..db import get_db
from ..deps import get_current_user, get_patient, require_medical
from ..models import (
    Attachment,
    AttachmentKind,
    BodyMark,
    Finding,
    Patient,
    TherapyGoal,
    Treatment,
    User,
)
from ..schemas import (
    AttachmentOut,
    AttachmentUpdate,
    BodyMarkIn,
    BodyMarkOut,
    BodyMarkUpdate,
    FindingIn,
    FindingOut,
    FindingUpdate,
    GoalIn,
    GoalOut,
    GoalUpdate,
    VoidIn,
)
from .medical import _ensure_not_voided, _get_entry, _void

router = APIRouter(prefix="/api/patients/{patient_id}", tags=["documentation"], dependencies=[Depends(require_medical)])


def _check_treatment(db: Session, patient: Patient, treatment_id: int | None) -> None:
    if treatment_id is None:
        return
    t = db.get(Treatment, treatment_id)
    if not t or t.patient_id != patient.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Behandlung gehört nicht zu diesem Patienten")


def _list(db: Session, model, patient: Patient, *order):
    return db.scalars(select(model).where(model.patient_id == patient.id).order_by(*order)).all()


def _fields(model_cls) -> list[str]:
    return list(model_cls.model_fields)


# --- Befunde -------------------------------------------------------------------


@router.get("/findings", response_model=list[FindingOut])
def list_findings(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return _list(db, Finding, patient, Finding.recorded_on.desc(), Finding.id.desc())


@router.post("/findings", response_model=FindingOut, status_code=status.HTTP_201_CREATED)
def create_finding(data: FindingIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_treatment(db, patient, data.treatment_id)
    entry = Finding(**data.model_dump(), patient_id=patient.id, created_by_id=user.id)
    db.add(entry)
    db.flush()
    audit.log(db, user, "create", "finding", entry.id, patient.id, changes=audit.snapshot(entry, _fields(FindingIn)))
    db.commit()
    return entry


@router.put("/findings/{entry_id}", response_model=FindingOut)
def update_finding(
    entry_id: int,
    data: FindingUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = _get_entry(db, Finding, entry_id, patient)
    _ensure_not_voided(entry)
    _check_treatment(db, patient, data.treatment_id)
    diff = audit.apply_changes(entry, data.model_dump(exclude={"correction_reason"}))
    if diff:
        audit.log(db, user, "correct", "finding", entry.id, patient.id, changes=diff, reason=data.correction_reason)
    db.commit()
    return entry


@router.post("/findings/{entry_id}/void", response_model=FindingOut)
def void_finding(entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _void(db, _get_entry(db, Finding, entry_id, patient), "finding", data.reason, user)


# --- Körperatlas ----------------------------------------------------------------


@router.get("/body-marks", response_model=list[BodyMarkOut])
def list_marks(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return _list(db, BodyMark, patient, BodyMark.recorded_on.desc(), BodyMark.id.desc())


@router.post("/body-marks", response_model=BodyMarkOut, status_code=status.HTTP_201_CREATED)
def create_mark(data: BodyMarkIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_treatment(db, patient, data.treatment_id)
    entry = BodyMark(**data.model_dump(), patient_id=patient.id, created_by_id=user.id)
    db.add(entry)
    db.flush()
    audit.log(db, user, "create", "body_mark", entry.id, patient.id, changes=audit.snapshot(entry, _fields(BodyMarkIn)))
    db.commit()
    return entry


@router.put("/body-marks/{entry_id}", response_model=BodyMarkOut)
def update_mark(
    entry_id: int,
    data: BodyMarkUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = _get_entry(db, BodyMark, entry_id, patient)
    _ensure_not_voided(entry)
    _check_treatment(db, patient, data.treatment_id)
    diff = audit.apply_changes(entry, data.model_dump())
    if diff:
        audit.log(db, user, "update", "body_mark", entry.id, patient.id, changes=diff)
    db.commit()
    return entry


@router.post("/body-marks/{entry_id}/void", response_model=BodyMarkOut)
def void_mark(entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _void(db, _get_entry(db, BodyMark, entry_id, patient), "body_mark", data.reason, user)


# --- Dateien ------------------------------------------------------------------


def _attachment_out(a: Attachment) -> AttachmentOut:
    out = AttachmentOut.model_validate(a)
    out.has_thumb = a.thumb_path is not None
    return out


@router.get("/attachments", response_model=list[AttachmentOut])
def list_attachments(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return [_attachment_out(a) for a in _list(db, Attachment, patient, Attachment.taken_on.desc(), Attachment.id.desc())]


@router.post("/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    kind: AttachmentKind = Form(...),
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    taken_on: date | None = Form(None),
    treatment_id: int | None = Form(None),
    parent_id: int | None = Form(None),
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _check_treatment(db, patient, treatment_id)
    if parent_id is not None:
        parent = db.get(Attachment, parent_id)
        if not parent or parent.patient_id != patient.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Ursprungsdatei gehört nicht zu diesem Patienten")
    limit = storage.get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    stored = storage.save_upload(patient.id, data)
    if kind != AttachmentKind.document and stored.content_type == "application/pdf":
        Path(storage.resolve(stored.path)).unlink(missing_ok=True)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "PDF nur als Dokument")
    entry = Attachment(
        patient_id=patient.id,
        treatment_id=treatment_id,
        parent_id=parent_id,
        created_by_id=user.id,
        kind=kind,
        caption=(caption or "").strip() or None,
        taken_on=taken_on or date.today(),
        filename=(file.filename or "datei")[:255],
        content_type=stored.content_type,
        size=stored.size,
        sha256=stored.sha256,
        path=stored.path,
        thumb_path=stored.thumb_path,
    )
    db.add(entry)
    db.flush()
    audit.log(
        db, user, "create", "attachment", entry.id, patient.id,
        changes={"kind": kind.value, "filename": entry.filename, "size": entry.size, "sha256": entry.sha256},
    )
    db.commit()
    return _attachment_out(entry)


@router.patch("/attachments/{entry_id}", response_model=AttachmentOut)
def update_attachment(
    entry_id: int,
    data: AttachmentUpdate,
    patient: Patient = Depends(get_patient),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = _get_entry(db, Attachment, entry_id, patient)
    _ensure_not_voided(entry)
    fields = data.model_dump(exclude_unset=True)
    _check_treatment(db, patient, fields.get("treatment_id"))
    diff = audit.apply_changes(entry, fields)
    if diff:
        audit.log(db, user, "update", "attachment", entry.id, patient.id, changes=diff)
    db.commit()
    return _attachment_out(entry)


@router.post("/attachments/{entry_id}/void", response_model=AttachmentOut)
def void_attachment(entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _attachment_out(_void(db, _get_entry(db, Attachment, entry_id, patient), "attachment", data.reason, user))


def _serve(entry: Attachment, relative: str, content_type: str, filename: str, inline: bool = True) -> FileResponse:
    path = storage.resolve(relative)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Datei nicht gefunden")
    disposition = "inline" if inline else "attachment"
    return FileResponse(
        path,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename.encode("ascii", "ignore").decode() or "datei"}"',
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'",
        },
    )


@router.get("/attachments/{entry_id}/file")
def attachment_file(entry_id: int, download: bool = False, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = _get_entry(db, Attachment, entry_id, patient)
    audit.log(db, user, "view", "attachment", entry.id, patient.id)
    db.commit()
    return _serve(entry, entry.path, entry.content_type, entry.filename, inline=not download)


@router.get("/attachments/{entry_id}/thumb")
def attachment_thumb(entry_id: int, patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    entry = _get_entry(db, Attachment, entry_id, patient)
    if not entry.thumb_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Keine Vorschau")
    return _serve(entry, entry.thumb_path, "image/jpeg", "vorschau.jpg")


# --- Therapieziele --------------------------------------------------------------


@router.get("/goals", response_model=list[GoalOut])
def list_goals(patient: Patient = Depends(get_patient), db: Session = Depends(get_db)):
    return _list(db, TherapyGoal, patient, TherapyGoal.created_at.desc())


def _goal_dates(data: GoalIn | GoalUpdate) -> dict:
    values = data.model_dump()
    if data.status.value == "achieved" and not data.achieved_on:
        values["achieved_on"] = date.today()
    if data.status.value != "achieved":
        values["achieved_on"] = None
    return values


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = TherapyGoal(**_goal_dates(data), patient_id=patient.id, created_by_id=user.id)
    db.add(entry)
    db.flush()
    audit.log(db, user, "create", "goal", entry.id, patient.id, changes=audit.snapshot(entry, _fields(GoalIn)))
    db.commit()
    return entry


@router.put("/goals/{entry_id}", response_model=GoalOut)
def update_goal(entry_id: int, data: GoalUpdate, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = _get_entry(db, TherapyGoal, entry_id, patient)
    _ensure_not_voided(entry)
    diff = audit.apply_changes(entry, _goal_dates(data))
    if diff:
        audit.log(db, user, "update", "goal", entry.id, patient.id, changes=diff)
    db.commit()
    return entry


@router.post("/goals/{entry_id}/void", response_model=GoalOut)
def void_goal(entry_id: int, data: VoidIn, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _void(db, _get_entry(db, TherapyGoal, entry_id, patient), "goal", data.reason, user)
