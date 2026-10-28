"""Vorlagen aus der Datenbank (pflegbar durch den Administrator) mit Seed aus den Standardwerten in catalog.py."""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import catalog as defaults
from .models import CatalogItem

KINDS = ("red_flag", "yellow_flag", "measure", "finding_preset")
CATEGORIES = ("rom", "strength", "test", "measure")


def slugify(text: str) -> str:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:60] or "eintrag"


def ensure_seeded(db: Session) -> None:
    """Legt die Standardvorlagen an, solange die Tabelle noch leer ist (alle als "ungeprüft")."""
    if db.scalar(select(func.count(CatalogItem.id))):
        return
    order = 0

    def add(**kw):
        nonlocal order
        order += 10
        db.add(CatalogItem(sort_order=order, active=True, reviewed=False, **kw))

    for key, label in defaults.RED_FLAGS.items():
        add(kind="red_flag", key=key, label=label)
    for key, label in defaults.YELLOW_FLAGS.items():
        add(kind="yellow_flag", key=key, label=label)
    for name in defaults.MEASURES:
        add(kind="measure", key=name, label=name)
    for category, name, unit in defaults.FINDING_PRESETS:
        norm = defaults.ROM_NORMS.get(name)
        add(
            kind="finding_preset", key=name, label=name, category=category, unit=unit,
            norm_opposite=norm[0] if norm else None, norm_neutral=norm[1] if norm else None, norm_main=norm[2] if norm else None,
        )
    db.commit()


def items(db: Session, kind: str, only_active: bool = True) -> list[CatalogItem]:
    ensure_seeded(db)
    stmt = select(CatalogItem).where(CatalogItem.kind == kind).order_by(CatalogItem.sort_order, CatalogItem.id)
    if only_active:
        stmt = stmt.where(CatalogItem.active.is_(True))
    return list(db.scalars(stmt))


def known_keys(db: Session, kind: str) -> set[str]:
    """Alle Schlüssel, auch deaktivierte (ältere Akten dürfen sie weiter enthalten)."""
    return {i.key for i in items(db, kind, only_active=False)}


def unique_key(db: Session, kind: str, label: str) -> str:
    base = slugify(label) if kind in ("red_flag", "yellow_flag") else label.strip()
    taken = known_keys(db, kind)
    key, n = base, 2
    while key in taken:
        key = f"{base}_{n}" if kind in ("red_flag", "yellow_flag") else f"{base} ({n})"
        n += 1
    return key
