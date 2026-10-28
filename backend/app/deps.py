from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Patient, Role, User, UserSession
from .security import hash_token

SESSION_COOKIE = "physioflow_session"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
        if session and _aware(session.expires_at) > datetime.now(timezone.utc) and session.user.is_active:
            return session.user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Administratoren")
    return user


def get_patient(patient_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient nicht gefunden")
    return patient


def _aware(dt: datetime) -> datetime:
    # SQLite liefert naive Zeitstempel zurück; gespeichert wird immer UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
