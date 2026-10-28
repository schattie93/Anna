"""Betriebsfunktionen: Integritätsprüfung, Backup-Status, Aufbewahrung/Löschung, Akten-Export."""

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import delete, func, inspect, select, text, update
from sqlalchemy.orm import Session

from . import storage
from .config import get_settings
from .models import (
    Anamnesis,
    Appointment,
    Attachment,
    AuditEntry,
    BodyMark,
    Diagnosis,
    ExercisePlan,
    ExercisePlanItem,
    Finding,
    FollowUp,
    Invoice,
    InvoiceItem,
    Patient,
    Payment,
    Prescription,
    Setting,
    TherapyGoal,
    Treatment,
    User,
)
from .timeutil import local_today

OPS_KEYS = ("last_backup_at", "last_backup_file", "last_restore_test_at")


def get_ops(db: Session) -> dict[str, str | None]:
    stored = {s.key: s.value for s in db.scalars(select(Setting).where(Setting.key.in_(OPS_KEYS)))}
    return {k: stored.get(k) for k in OPS_KEYS}


def set_ops(db: Session, key: str, value: str) -> None:
    assert key in OPS_KEYS
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


# --- Integrität ---------------------------------------------------------------------


def head_revision() -> str | None:
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def check_integrity(db: Session, verify_hashes: bool = True) -> dict:
    """Prüft Datenbankstand, Dateien (vorhanden + Prüfsumme) und die Lückenlosigkeit der Rechnungsnummern."""
    problems: list[str] = []
    info: dict = {}

    try:
        current = db.execute(text("select version_num from alembic_version")).scalar()
    except Exception:
        current = None
    head = head_revision()
    info["schema"] = {"current": current, "head": head}
    if current != head:
        problems.append(f"Datenbankschema nicht aktuell (ist {current}, erwartet {head})")

    checked = 0
    for a in db.scalars(select(Attachment)):
        for rel in (a.path, a.thumb_path):
            if rel and not storage.resolve(rel).is_file():
                problems.append(f"Datei fehlt: Eintrag {a.id} ({rel})")
        if verify_hashes and a.path and storage.resolve(a.path).is_file():
            if hashlib.sha256(storage.resolve(a.path).read_bytes()).hexdigest() != a.sha256:
                problems.append(f"Prüfsumme stimmt nicht: Datei-Eintrag {a.id}")
            checked += 1
    info["files_hash_checked"] = checked

    seqs: dict[int, list[int]] = {}
    for year, seq in db.execute(select(Invoice.year, Invoice.seq).where(Invoice.seq.is_not(None))):
        seqs.setdefault(year, []).append(seq)
    for year, values in seqs.items():
        if sorted(values) != list(range(1, len(values) + 1)):
            problems.append(f"Rechnungsnummern {year} nicht lückenlos")

    info["counts"] = {
        "patients": db.scalar(select(func.count(Patient.id))),
        "treatments": db.scalar(select(func.count(Treatment.id))),
        "attachments": db.scalar(select(func.count(Attachment.id))),
        "invoices": db.scalar(select(func.count(Invoice.id))),
        "users": db.scalar(select(func.count(User.id))),
    }
    return {"ok": not problems, "problems": problems, **info}


# --- Aufbewahrung & Löschung -----------------------------------------------------------


def last_activity(db: Session, p: Patient) -> date:
    candidates = [p.created_at.date()]
    for model, column in (
        (Treatment, Treatment.treated_on),
        (Prescription, Prescription.issued_on),
        (Invoice, Invoice.issue_date),
        (Attachment, Attachment.taken_on),
        (Finding, Finding.recorded_on),
        (Anamnesis, Anamnesis.recorded_on),
    ):
        latest = db.scalar(select(func.max(column)).where(model.patient_id == p.id))
        if latest:
            candidates.append(latest)
    return max(candidates)


def retention_candidates(db: Session) -> list[dict]:
    years = get_settings().retention_years
    today = local_today()
    out = []
    for p in db.scalars(select(Patient).order_by(Patient.last_name)):
        last = last_activity(db, p)
        try:
            due = last.replace(year=last.year + years)
        except ValueError:  # 29. Februar
            due = last.replace(year=last.year + years, day=28)
        out.append({"patient": p, "last_activity": last, "retention_until": due, "eligible": due < today})
    return sorted(out, key=lambda r: r["retention_until"])


def _delete_stored(rel: str | None) -> None:
    if rel:
        storage.resolve(rel).unlink(missing_ok=True)


def erase_patient(db: Session, patient: Patient, admin: User, reason: str) -> dict:
    """Löscht Patient und alle zugehörigen Daten unwiderruflich (inkl. Dateien und Protokolleinträge). Hinterlässt nur einen
    Protokolleintrag ohne personenbezogene Daten (Patientennummer, Anzahl, Begründung)."""
    pid = patient.id
    number = patient.patient_number
    counts = {
        "treatments": db.scalar(select(func.count(Treatment.id)).where(Treatment.patient_id == pid)),
        "attachments": db.scalar(select(func.count(Attachment.id)).where(Attachment.patient_id == pid)),
        "invoices": db.scalar(select(func.count(Invoice.id)).where(Invoice.patient_id == pid)),
    }
    for a in db.scalars(select(Attachment).where(Attachment.patient_id == pid)):
        _delete_stored(a.path)
        _delete_stored(a.thumb_path)

    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("select set_config('physioflow.allow_audit_purge', 'on', true)"))

    db.execute(delete(Appointment).where(Appointment.patient_id == pid))
    db.execute(delete(Finding).where(Finding.patient_id == pid))
    db.execute(delete(BodyMark).where(BodyMark.patient_id == pid))
    db.execute(update(Attachment).where(Attachment.patient_id == pid).values(parent_id=None))
    db.execute(delete(Attachment).where(Attachment.patient_id == pid))
    db.execute(delete(TherapyGoal).where(TherapyGoal.patient_id == pid))
    db.execute(delete(FollowUp).where(FollowUp.patient_id == pid))
    plan_ids = select(ExercisePlan.id).where(ExercisePlan.patient_id == pid)
    db.execute(delete(ExercisePlanItem).where(ExercisePlanItem.plan_id.in_(plan_ids)))
    db.execute(delete(ExercisePlan).where(ExercisePlan.patient_id == pid))
    inv_ids = select(Invoice.id).where(Invoice.patient_id == pid)
    db.execute(delete(Payment).where(Payment.invoice_id.in_(inv_ids)))
    db.execute(delete(InvoiceItem).where(InvoiceItem.invoice_id.in_(inv_ids)))
    db.execute(update(Invoice).where(Invoice.patient_id == pid).values(cancels_id=None))
    db.execute(delete(Invoice).where(Invoice.patient_id == pid))
    db.execute(delete(Treatment).where(Treatment.patient_id == pid))
    db.execute(delete(Prescription).where(Prescription.patient_id == pid))
    db.execute(delete(Diagnosis).where(Diagnosis.patient_id == pid))
    db.execute(delete(Anamnesis).where(Anamnesis.patient_id == pid))
    db.execute(delete(AuditEntry).where(AuditEntry.patient_id == pid))
    db.execute(delete(Patient).where(Patient.id == pid))
    db.add(
        AuditEntry(
            user_id=admin.id, action="erase", entity_type="patient", entity_id=pid, patient_id=None,
            changes={"patient_number": number, **counts}, reason=reason,
        )
    )
    folder = storage.root() / str(pid)
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
    return {"patient_number": number, **counts}


# --- Export ------------------------------------------------------------------------


def _plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def row_dict(obj) -> dict:
    return {c.key: _plain(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs if c.key not in {"password_hash"}}


def export_record(db: Session, patient: Patient) -> tuple[dict, list[Attachment]]:
    pid = patient.id

    def rows(model, order=None):
        stmt = select(model).where(model.patient_id == pid)
        return [row_dict(r) for r in db.scalars(stmt.order_by(order) if order is not None else stmt)]

    invoices = []
    for inv in db.scalars(select(Invoice).where(Invoice.patient_id == pid).order_by(Invoice.id)):
        d = row_dict(inv)
        d["number"] = inv.number
        d["items"] = [row_dict(i) for i in inv.items]
        d["payments"] = [row_dict(p) for p in inv.payments]
        invoices.append(d)
    plans = []
    for plan in db.scalars(select(ExercisePlan).where(ExercisePlan.patient_id == pid)):
        d = row_dict(plan)
        d["items"] = [row_dict(i) for i in plan.items]
        plans.append(d)
    attachments = list(db.scalars(select(Attachment).where(Attachment.patient_id == pid).order_by(Attachment.id)))
    history = [row_dict(a) for a in db.scalars(select(AuditEntry).where(AuditEntry.patient_id == pid, AuditEntry.action != "view").order_by(AuditEntry.id))]
    data = {
        "format": "physioflow-akte-v1",
        "exported_at": datetime.now().astimezone().isoformat(),
        "patient": row_dict(patient),
        "anamneses": rows(Anamnesis),
        "diagnoses": rows(Diagnosis),
        "treatments": rows(Treatment),
        "findings": rows(Finding),
        "body_marks": rows(BodyMark),
        "attachments": [{**row_dict(a), "archive_path": f"dateien/{a.id}_{Path(a.path).name}"} for a in attachments],
        "goals": rows(TherapyGoal),
        "prescriptions": rows(Prescription),
        "appointments": rows(Appointment),
        "follow_ups": rows(FollowUp),
        "exercise_plans": plans,
        "invoices": invoices,
        "change_history": history,
    }
    return json.loads(json.dumps(data, default=_plain)), attachments
