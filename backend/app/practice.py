"""Praxisdaten (Briefkopf, Bankverbindung …) aus der Tabelle settings."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Setting

PRACTICE_FIELDS: dict[str, str] = {
    "practice_name": "Praxisname",
    "practice_owner": "Inhaber/in",
    "practice_address": "Adresse",
    "practice_phone": "Telefon",
    "practice_email": "E-Mail",
    "practice_tax_number": "Steuernummer",
    "practice_ik": "Institutionskennzeichen (IK)",
    "practice_iban": "IBAN",
    "practice_bic": "BIC",
    "practice_bank": "Bank",
    "invoice_vat_note": "Umsatzsteuer-Hinweis",
    "invoice_payment_days": "Zahlungsziel (Tage)",
    "invoice_footer": "Fußzeile Rechnung",
}

DEFAULTS = {
    "practice_name": "Physiotherapie-Praxis",
    "invoice_vat_note": "Heilbehandlungen sind gemäß § 4 Nr. 14 UStG von der Umsatzsteuer befreit.",
    "invoice_payment_days": "14",
}


def get_practice(db: Session) -> dict[str, str | None]:
    stored = {s.key: s.value for s in db.scalars(select(Setting))}
    return {k: (stored.get(k) if stored.get(k) not in (None, "") else DEFAULTS.get(k)) for k in PRACTICE_FIELDS}


def save_practice(db: Session, values: dict[str, str | None]) -> dict[str, dict[str, str | None]]:
    """Schreibt Werte und gibt {schlüssel: {old, new}} der Änderungen zurück."""
    diff: dict[str, dict[str, str | None]] = {}
    current = {s.key: s for s in db.scalars(select(Setting))}
    for key, new in values.items():
        if key not in PRACTICE_FIELDS:
            continue
        new = (new or "").strip() or None
        row = current.get(key)
        old = row.value if row else None
        if old == new:
            continue
        diff[key] = {"old": old, "new": new}
        if row:
            row.value = new
        else:
            db.add(Setting(key=key, value=new))
    return diff
