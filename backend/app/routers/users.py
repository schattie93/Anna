from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import require_admin
from ..models import User, UserSession
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.full_name)).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Benutzername bereits vergeben")
    user = User(username=data.username, full_name=data.full_name, role=data.role, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    audit.log(db, admin, "create", "user", user.id, changes={"username": user.username, "role": user.role.value})
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benutzer nicht gefunden")
    if user.id == admin.id and (data.is_active is False or (data.role and data.role != admin.role)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Eigenes Konto kann nicht deaktiviert oder herabgestuft werden")
    fields = data.model_dump(exclude_unset=True, exclude={"password"})
    diff = audit.apply_changes(user, fields)
    if data.password:
        user.password_hash = hash_password(data.password)
        diff["password"] = {"old": "***", "new": "***"}
    if data.password or data.is_active is False:
        db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    if diff:
        audit.log(db, admin, "update", "user", user.id, changes=diff)
    db.commit()
    return user
