from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Patient, Role, User, UserSession
from .security import hash_token

SESSION_COOKIE = "physioflow_session"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        now = datetime.now(timezone.utc)
        session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
        if session and _aware(session.expires_at) > now and session.user.is_active:
            last = _aware(session.last_seen or session.created_at)
            if now - last > timedelta(minutes=get_settings().idle_minutes):
                db.delete(session)  # wegen Inaktivität abgelaufen
                db.commit()
            else:
                if now - last > timedelta(seconds=60):  # Aktivität höchstens einmal pro Minute festhalten
                    session.last_seen = now
                    db.commit()
                return session.user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Administratoren")
    return user


def require_medical(user: User = Depends(get_current_user)) -> User:
    """Zugriff auf medizinische Inhalte (Anamnese, Befunde, Behandlungen, Dateien …)."""
    if user.role == Role.reception:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung für medizinische Daten")
    return user


def get_patient(patient_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient nicht gefunden")
    return patient


def _aware(dt: datetime) -> datetime:
    # SQLite liefert naive Zeitstempel zurück; gespeichert wird immer UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
