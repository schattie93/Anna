from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import get_current_user, require_admin
from ..models import User
from ..practice import PRACTICE_FIELDS, get_practice, save_practice
from ..schemas import PracticeSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/practice", response_model=PracticeSettings)
def read_practice(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return get_practice(db)


@router.put("/practice", response_model=PracticeSettings)
def write_practice(data: PracticeSettings, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    diff = save_practice(db, data.model_dump())
    if diff:
        audit.log(db, admin, "update", "settings", changes=diff)
    db.commit()
    return get_practice(db)
