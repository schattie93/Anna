"""Auswertungen: Behandlungsstatistik, Dokumentationsvollständigkeit, Terminquoten."""

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_medical
from ..models import (
    Anamnesis,
    Appointment,
    AppointmentStatus,
    Diagnosis,
    InsuranceType,
    Patient,
    Treatment,
    TreatmentStatus,
)
from ..timeutil import day_range_utc, local_today

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(require_medical)])


@router.get("")
def stats(year: int | None = None, db: Session = Depends(get_db)):
    today = local_today()
    year = year or today.year
    active = Treatment.voided.is_(False)

    treatments = db.scalars(select(Treatment).where(active, Treatment.status == TreatmentStatus.final)).all()
    in_year = [t for t in treatments if t.treated_on.year == year]
    by_month = [0] * 12
    minutes = 0
    measures: Counter[str] = Counter()
    patients_per_month: list[set[int]] = [set() for _ in range(12)]
    for t in in_year:
        by_month[t.treated_on.month - 1] += 1
        patients_per_month[t.treated_on.month - 1].add(t.patient_id)
        minutes += t.duration_minutes or 0
        measures.update(t.measures)

    lo, _ = day_range_utc(today.replace(month=1, day=1, year=year))
    _, hi = day_range_utc(today.replace(month=12, day=31, year=year))
    appts = db.scalars(select(Appointment).where(Appointment.start >= lo, Appointment.start < hi, Appointment.patient_id.is_not(None))).all()
    counts = Counter(a.status.value for a in appts)
    scheduled = counts["done"] + counts["no_show"] + counts["cancelled"]

    # Dokumentationsvollständigkeit (Stand heute)
    stale = db.scalars(
        select(Treatment).where(active, Treatment.status == TreatmentStatus.draft, Treatment.treated_on < today - timedelta(days=1))
    ).all()
    gkv_without_rx = db.scalar(
        select(func.count(Treatment.id))
        .join(Patient, Patient.id == Treatment.patient_id)
        .where(active, Treatment.status == TreatmentStatus.final, Treatment.prescription_id.is_(None), Patient.insurance_type == InsuranceType.gkv)
    )
    active_patients = db.scalars(select(Patient).where(Patient.archived.is_(False))).all()
    with_anamnesis = {pid for (pid,) in db.execute(select(Anamnesis.patient_id).where(Anamnesis.voided.is_(False)))}
    with_diagnosis = {pid for (pid,) in db.execute(select(Diagnosis.patient_id).where(Diagnosis.voided.is_(False)))}
    treated = {t.patient_id for t in treatments}

    return {
        "year": year,
        "treatments_by_month": by_month,
        "patients_by_month": [len(s) for s in patients_per_month],
        "treatments_year": len(in_year),
        "treatment_minutes_year": minutes,
        "measures": measures.most_common(10),
        "appointments": {
            "done": counts["done"], "planned": counts["planned"], "cancelled": counts["cancelled"], "no_show": counts["no_show"],
            "no_show_rate": round(counts["no_show"] / scheduled, 3) if scheduled else None,
            "cancel_rate": round(counts["cancelled"] / scheduled, 3) if scheduled else None,
        },
        "documentation": {
            "active_patients": len(active_patients),
            "draft_treatments_overdue": [{"id": t.id, "patient_id": t.patient_id, "treated_on": t.treated_on} for t in stale],
            "gkv_treatments_without_prescription": gkv_without_rx,
            "patients_without_data_consent": [p.id for p in active_patients if not p.consent_data_processing],
            "treated_patients_without_anamnesis": [pid for pid in treated if pid not in with_anamnesis],
            "treated_patients_without_diagnosis": [pid for pid in treated if pid not in with_diagnosis],
        },
    }
