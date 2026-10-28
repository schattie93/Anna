"""Übertragung von Einträgen, die am Tablet ohne Verbindung erfasst wurden.

Nur Neuanlagen (Behandlung, Befund, Atlas-Markierung, Erstbefund, Anamnese, Unterschrift) sind offline möglich.
Korrekturen und Stornierungen brauchen die Verbindung (Begründung, Prüfung gegen den aktuellen Stand), so entstehen keine
Konflikte. Jede Übertragung ist wiederholbar: bereits verarbeitete Vorgänge werden nicht erneut angelegt.
"""

import base64
import binascii
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import get_current_user, require_medical
from ..models import ClientOp, Patient, User
from ..schemas import AnamnesisIn, BodyMarkIn, ExaminationIn, FindingIn, TreatmentIn
from . import documentation, medical

router = APIRouter(prefix="/api/sync", tags=["sync"], dependencies=[Depends(require_medical)])

Kind = Literal["create_treatment", "create_finding", "create_body_mark", "create_examination", "create_anamnesis", "sign_treatment"]
REF_FIELDS = ("treatment_id", "diagnosis_id", "prescription_id")


class SyncOp(BaseModel):
    op_id: str = Field(min_length=8, max_length=64)
    kind: Kind
    patient_id: int
    temp_id: int | None = None  # vorläufige (negative) Kennung auf dem Tablet
    client_time: datetime | None = None  # wann am Tablet erfasst
    data: dict[str, Any]


class SyncIn(BaseModel):
    ops: list[SyncOp] = Field(max_length=300)


class SyncResult(BaseModel):
    op_id: str
    temp_id: int | None
    ok: bool
    real_id: int | None = None
    error: str | None = None


class SyncOut(BaseModel):
    results: list[SyncResult]


def _resolve(db: Session, user: User, value: Any) -> Any:
    """Ersetzt eine vorläufige (negative) Kennung durch die echte, falls der Bezugseintrag schon übertragen wurde."""
    if isinstance(value, int) and value < 0:
        real = db.scalar(select(ClientOp.real_id).where(ClientOp.user_id == user.id, ClientOp.temp_id == value, ClientOp.ok.is_(True)))
        if real is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Der zugehörige Eintrag wurde noch nicht übertragen")
        return real
    return value


def _apply(db: Session, user: User, op: SyncOp) -> int:
    patient = db.get(Patient, op.patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient nicht gefunden")
    data = {k: (_resolve(db, user, v) if k in REF_FIELDS else v) for k, v in op.data.items()}
    try:
        if op.kind == "create_treatment":
            return medical.create_treatment(TreatmentIn.model_validate(data), patient, db, user).id
        if op.kind == "create_finding":
            return documentation.create_finding(FindingIn.model_validate(data), patient, db, user).id
        if op.kind == "create_body_mark":
            return documentation.create_mark(BodyMarkIn.model_validate(data), patient, db, user).id
        if op.kind == "create_examination":
            return medical.create_examination(ExaminationIn.model_validate(data), patient, db, user).id
        if op.kind == "create_anamnesis":
            return medical.create_anamnesis(AnamnesisIn.model_validate(data), patient, db, user).id
        # sign_treatment
        try:
            png = base64.b64decode(data["png_base64"], validate=True)
        except (KeyError, binascii.Error):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unterschrift fehlt oder ist beschädigt") from None
        return documentation.store_signature(db, patient, int(data["treatment_id"]), png, user).id
    except ValidationError as e:
        first = e.errors()[0]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{'.'.join(str(x) for x in first['loc'])}: {first['msg']}") from None


@router.post("", response_model=SyncOut)
def sync(body: SyncIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    results: list[SyncResult] = []
    for op in body.ops:
        done = db.scalar(select(ClientOp).where(ClientOp.user_id == user.id, ClientOp.op_id == op.op_id))
        if done:  # bereits verarbeitet (z. B. Antwort ging verloren): gleiches Ergebnis erneut melden
            results.append(SyncResult(op_id=op.op_id, temp_id=op.temp_id, ok=done.ok, real_id=done.real_id, error=done.error))
            continue
        try:
            real_id, ok, error = _apply(db, user, op), True, None
            audit.log(
                db, user, "sync", "signature" if op.kind == "sign_treatment" else op.kind.removeprefix("create_"), real_id, op.patient_id,
                changes={"op_id": op.op_id, "offline_erfasst_am": op.client_time.isoformat() if op.client_time else None},
            )
        except HTTPException as e:
            db.rollback()
            if e.status_code >= 500:
                raise
            real_id, ok, error = None, False, str(e.detail)
        db.add(ClientOp(user_id=user.id, op_id=op.op_id, kind=op.kind, temp_id=op.temp_id, real_id=real_id, ok=ok, error=error))
        db.commit()
        results.append(SyncResult(op_id=op.op_id, temp_id=op.temp_id, ok=ok, real_id=real_id, error=error))
    return SyncOut(results=results)
