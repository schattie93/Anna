from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..deps import SESSION_COOKIE, _aware, get_current_user
from ..models import Role, User, UserSession
from ..schemas import AuthStatus, LoginIn, PasswordChange, SetupIn, UserOut
from ..security import hash_password, hash_token, new_session_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _start_session(db: Session, user: User, response: Response) -> None:
    settings = get_settings()
    token = new_session_token()
    now = datetime.now(timezone.utc)
    db.execute(delete(UserSession).where(UserSession.expires_at < now))
    db.add(UserSession(token_hash=hash_token(token), user_id=user.id, expires_at=now + timedelta(hours=settings.session_hours)))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )


@router.get("/status", response_model=AuthStatus)
def auth_status(request: Request, db: Session = Depends(get_db)):
    setup_required = db.scalar(select(func.count(User.id))) == 0
    try:
        user = get_current_user(request, db)
    except HTTPException:
        user = None
    return AuthStatus(setup_required=setup_required, user=user)


@router.post("/setup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def initial_setup(data: SetupIn, response: Response, db: Session = Depends(get_db)):
    """Legt beim allerersten Start das Administratorkonto an."""
    if db.scalar(select(func.count(User.id))) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Einrichtung bereits abgeschlossen")
    user = User(username=data.username, full_name=data.full_name, password_hash=hash_password(data.password), role=Role.admin)
    db.add(user)
    db.flush()
    audit.log(db, user, "setup", "user", user.id)
    _start_session(db, user, response)
    db.commit()
    return user


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.username == data.username))
    if user and user.locked_until and _aware(user.locked_until) > now:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Konto vorübergehend gesperrt – bitte später erneut versuchen")
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_attempts = 0
        audit.log(db, None, "login_failed", "user", user.id if user else None, changes={"username": data.username})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Benutzername oder Passwort falsch")
    user.failed_attempts = 0
    user.locked_until = None
    audit.log(db, user, "login", "user", user.id)
    _start_session(db, user, response)
    db.commit()
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aktuelles Passwort ist falsch")
    user.password_hash = hash_password(data.new_password)
    audit.log(db, user, "password_change", "user", user.id)
    db.commit()
