"""Prüfhinweise zu Heilmittelverordnungen (Fristen, Unterbrechungen, Einheiten).

Die Regeln sind Hilfen und ersetzen nicht die Prüfung nach der aktuellen Heilmittel-Richtlinie.
Die Fristen sind in config.py einstellbar.
"""

from datetime import date, timedelta

from .config import get_settings
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import IndicationEntry, Prescription, Treatment, TreatmentStatus
from .timeutil import local_today


def catalog_warnings(db: Session, rx: Prescription) -> list[dict[str, str]]:
    """Mengenprüfung anhand des von der Praxis gepflegten Heilmittelkatalogs."""
    if not rx.indication_key:
        return []
    key = rx.indication_key.strip().upper()
    entry = db.scalars(select(IndicationEntry).where(IndicationEntry.key == key, IndicationEntry.active.is_(True))).first()
    if not entry:
        return [{"level": "info", "text": f"Indikationsschlüssel {key} ist im Heilmittelkatalog der Praxis nicht gepflegt – Mengenprüfung nicht möglich."}]
    out: list[dict[str, str]] = []
    if entry.max_units_per_rx and rx.total_units > entry.max_units_per_rx:
        out.append({"level": "warn", "text": f"Verordnete Menge ({rx.total_units}) überschreitet die Höchstmenge je Verordnung ({entry.max_units_per_rx}) für {key}."})
    if entry.orienting_total_units:
        same = db.scalars(
            select(Prescription).where(
                Prescription.patient_id == rx.patient_id, Prescription.voided.is_(False),
                Prescription.issued_on <= rx.issued_on, Prescription.indication_key.ilike(key),
            )
        ).all()
        total = sum(r.total_units for r in same)
        if total > entry.orienting_total_units:
            out.append({"level": "info", "text": f"Gesamtmenge für {key} ({total}) liegt über der orientierenden Behandlungsmenge ({entry.orienting_total_units}) – Verordnung außerhalb des Regelfalls: Begründung prüfen."})
    return out


def evaluate(rx: Prescription, treatments: list[Treatment], today: date | None = None, db: Session | None = None) -> dict:
    cfg = get_settings()
    today = today or local_today()
    mine = [t for t in treatments if t.prescription_id == rx.id and not t.voided]
    done = sum(1 for t in mine if t.status == TreatmentStatus.final)
    dates = sorted(t.treated_on for t in mine)
    latest_start = rx.issued_on + timedelta(days=cfg.rx_urgent_start_days if rx.urgent else cfg.rx_start_days)
    remaining = max(rx.total_units - done, 0)

    warnings: list[dict[str, str]] = []
    status = "open"
    if done >= rx.total_units:
        status = "completed"
    elif not dates and today > latest_start:
        status = "expired"
        warnings.append({"level": "warn", "text": f"Behandlungsbeginn bis {latest_start:%d.%m.%Y} nicht erfolgt – Verordnung nicht mehr gültig."})
    if dates and dates[0] > latest_start:
        warnings.append({"level": "warn", "text": f"Erste Behandlung ({dates[0]:%d.%m.%Y}) nach Ablauf der Beginn-Frist ({latest_start:%d.%m.%Y})."})
    for a, b in zip(dates, dates[1:]):
        gap = (b - a).days
        if gap > cfg.rx_max_break_days:
            warnings.append({"level": "warn", "text": f"Unterbrechung von {gap} Tagen zwischen {a:%d.%m.%Y} und {b:%d.%m.%Y} (max. {cfg.rx_max_break_days})."})
    if status == "open" and dates and (today - dates[-1]).days > cfg.rx_max_break_days:
        warnings.append({"level": "warn", "text": f"Seit {(today - dates[-1]).days} Tagen keine Behandlung – Unterbrechungsfrist ({cfg.rx_max_break_days} Tage) überschritten."})
    if len(mine) > rx.total_units:
        warnings.append({"level": "warn", "text": f"{len(mine)} Behandlungen zugeordnet, verordnet sind {rx.total_units}."})
    if status == "open" and 0 < remaining <= 2:
        warnings.append({"level": "info", "text": f"Noch {remaining} Einheit(en) – Folgeverordnung rechtzeitig anfordern."})
    if status == "open" and not dates and (latest_start - today).days <= 7:
        warnings.append({"level": "info", "text": f"Behandlungsbeginn spätestens bis {latest_start:%d.%m.%Y}."})

    if db is not None:
        warnings.extend(catalog_warnings(db, rx))

    return {
        "units_done": done,
        "units_remaining": remaining,
        "status": status,
        "latest_start": latest_start,
        "warnings": warnings,
    }
