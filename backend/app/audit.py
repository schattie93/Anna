from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditEntry, User


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def apply_changes(obj: Any, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Setzt die Felder und gibt nur die tatsächlich geänderten Werte als {feld: {old, new}} zurück."""
    diff: dict[str, dict[str, Any]] = {}
    for field, new in data.items():
        old = getattr(obj, field)
        if _plain(old) != _plain(new):
            diff[field] = {"old": _plain(old), "new": _plain(new)}
            setattr(obj, field, new)
    return diff


def snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {f: _plain(getattr(obj, f)) for f in fields}


def log(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    patient_id: int | None = None,
    changes: dict | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        AuditEntry(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            patient_id=patient_id,
            changes=changes,
            reason=reason,
        )
    )
