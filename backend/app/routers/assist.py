"""Lokale Assistenz-Endpunkte (Sprache, OCR, Textvorschläge). Verarbeitung nur im Praxisnetz, siehe assist.py."""

from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import assist, audit, storage
from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user, get_patient, require_medical
from ..models import Anamnesis, Attachment, Diagnosis, Finding, Patient, TherapyGoal, Treatment, TreatmentStatus, User
from ..schemas import AssistStatus, AttachmentOut, DraftOut, SoapOut, SuggestIn, TextOut
from .medical import _ensure_not_voided, _get_entry

router = APIRouter(prefix="/api", tags=["assist"], dependencies=[Depends(require_medical)])

SEX = {"female": "weiblich", "male": "männlich", "diverse": "divers", "unknown": "Geschlecht unbekannt"}


def _read_limit() -> int:
    return get_settings().max_upload_mb * 1024 * 1024


@router.get("/assist/status", response_model=AssistStatus)
def assist_status():
    return assist.status_info()


@router.post("/assist/transcribe", response_model=TextOut)
async def transcribe(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not (file.content_type or "").startswith(("audio/", "video/webm", "video/mp4")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nur Audiodateien erlaubt")
    data = await file.read(_read_limit() + 1)
    if not data or len(data) > _read_limit():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Audio leer oder zu groß")
    text = assist.transcribe(data, file.filename or "audio.webm", file.content_type or "audio/webm")
    audit.log(db, user, "assist", "transcribe", changes={"bytes": len(data), "chars": len(text)})
    db.commit()
    return TextOut(text=text)


@router.post("/assist/ocr", response_model=TextOut)
async def ocr_upload(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = await file.read(_read_limit() + 1)
    if not data or len(data) > _read_limit():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Datei leer oder zu groß")
    text = assist.ocr(data, is_pdf=data[:5] == b"%PDF-")
    audit.log(db, user, "assist", "ocr", changes={"bytes": len(data), "chars": len(text)})
    db.commit()
    return TextOut(text=text)


@router.post("/assist/polish", response_model=DraftOut)
def polish(data: SuggestIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    out = assist.suggest("polish", data.text)
    audit.log(db, user, "assist", "polish", changes={"chars_in": len(data.text), "chars_out": len(out)})
    db.commit()
    return DraftOut(text=out)


@router.post("/assist/soap", response_model=SoapOut)
def soap(data: SuggestIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    raw = assist.suggest("soap", data.text)
    audit.log(db, user, "assist", "soap", changes={"chars_in": len(data.text)})
    db.commit()
    return SoapOut(**assist.parse_soap(raw))


@router.post("/patients/{patient_id}/attachments/{entry_id}/ocr", response_model=AttachmentOut)
def ocr_attachment(
    entry_id: int, patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Erkennt den Text einer gespeicherten Datei und legt ihn zur Korrektur am Eintrag ab."""
    entry = _get_entry(db, Attachment, entry_id, patient)
    _ensure_not_voided(entry)
    data = storage.resolve(entry.path).read_bytes()
    entry.ocr_text = assist.ocr(data, is_pdf=entry.content_type == "application/pdf")
    audit.log(db, user, "assist", "ocr", entry.id, patient.id, changes={"chars": len(entry.ocr_text)})
    db.commit()
    out = AttachmentOut.model_validate(entry)
    out.has_thumb = entry.thumb_path is not None
    return out


def _age(born: date) -> int:
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def report_context(db: Session, patient: Patient) -> str:
    """Verlaufsdaten ohne Name, Adresse oder Versichertennummer (Datenminimierung)."""
    lines = [f"Patient/in: {_age(patient.birth_date)} Jahre, {SEX[patient.sex.value]}"]
    diagnoses = db.scalars(select(Diagnosis).where(Diagnosis.patient_id == patient.id, Diagnosis.voided.is_(False)).order_by(Diagnosis.is_primary.desc())).all()
    if diagnoses:
        lines.append("Diagnosen: " + "; ".join(f"{d.description}{' (' + d.icd10_code + ')' if d.icd10_code else ''}" for d in diagnoses))
    an = db.scalars(select(Anamnesis).where(Anamnesis.patient_id == patient.id, Anamnesis.voided.is_(False)).order_by(Anamnesis.recorded_on)).first()
    if an:
        lines.append(f"Beschwerden bei Aufnahme: {an.chief_complaint}" + (f"; Schmerz {an.pain_current}/10" if an.pain_current is not None else ""))
        if an.goals:
            lines.append(f"Therapieziele: {an.goals}")
    ts = db.scalars(select(Treatment).where(Treatment.patient_id == patient.id, Treatment.voided.is_(False), Treatment.status == TreatmentStatus.final).order_by(Treatment.treated_on)).all()
    if ts:
        lines.append(f"Behandlungen: {len(ts)} (vom {ts[0].treated_on:%d.%m.%Y} bis {ts[-1].treated_on:%d.%m.%Y})")
        measures = Counter(m for t in ts for m in t.measures)
        if measures:
            lines.append("Häufigste Maßnahmen: " + ", ".join(m for m, _ in measures.most_common(4)))
        pains = [(t.pain_before, t.pain_after) for t in ts]
        first, last = pains[0], pains[-1]
        lines.append(f"Schmerz (NRS) erste Behandlung vor/nach: {first[0]}/{first[1]}; letzte Behandlung vor/nach: {last[0]}/{last[1]}")
        notes = [f"- {t.treated_on:%d.%m.}: {t.assessment}" for t in ts[-3:] if t.assessment]
        if notes:
            lines.append("Beurteilungen der letzten Behandlungen:\n" + "\n".join(notes))
    findings = db.scalars(select(Finding).where(Finding.patient_id == patient.id, Finding.voided.is_(False)).order_by(Finding.recorded_on)).all()
    series: dict[tuple[str, str], list[Finding]] = {}
    for f in findings:
        series.setdefault((f.name, f.side.value), []).append(f)
    for (name, side), items in series.items():
        if len(items) >= 2:
            def v(f: Finding) -> str:
                return f.value_text or f"{f.value_num:g}{' ' + f.unit if f.unit else ''}"
            lines.append(f"Befund {name}{'' if side == 'none' else ' ' + side}: {v(items[0])} -> {v(items[-1])}")
    goals = db.scalars(select(TherapyGoal).where(TherapyGoal.patient_id == patient.id, TherapyGoal.voided.is_(False))).all()
    if goals:
        names = {"open": "offen", "achieved": "erreicht", "dropped": "verworfen"}
        lines.append("Ziele: " + "; ".join(f"{g.description} ({names[g.status.value]})" for g in goals))
    return "\n".join(lines)


@router.post("/patients/{patient_id}/assist/report-draft", response_model=DraftOut)
def report_draft(patient: Patient = Depends(get_patient), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    text = assist.suggest("report", report_context(db, patient))
    audit.log(db, user, "assist", "report_draft", None, patient.id, changes={"chars_out": len(text)})
    db.commit()
    return DraftOut(text=text)
