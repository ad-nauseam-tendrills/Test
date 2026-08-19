from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/settings", tags=["settings"])


class UpdateSettingsRequest(BaseModel):
    artwork_integrity_enabled: bool


@router.get("", response_model=UserRead)
def get_settings(current_user: User = Depends(get_current_user)):
    return UserRead.model_validate(current_user)


@router.put("", response_model=UserRead)
def update_settings(
    payload: UpdateSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.artwork_integrity_enabled = payload.artwork_integrity_enabled
    db.commit()
    db.refresh(current_user)
    return UserRead.model_validate(current_user)
