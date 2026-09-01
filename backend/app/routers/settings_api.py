from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..routers.auth import CurrentUser, get_current_user, require_admin
from ..services.settings_service import get_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def read_settings(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    return get_settings(db)


@router.put("")
def write_settings(body: dict, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_admin)):
    return update_settings(db, body)