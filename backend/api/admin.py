from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import AuthService, require_admin
from ..config import Settings, get_settings
from ..database import get_db
from ..models import User
from ..schemas import AdminPasswordReset, AdminUserCreate, AdminUserUpdate, UserOut


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[UserOut]:
    return AuthService(database, settings).list_users()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: AdminUserCreate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    return AuthService(database, settings).create_user(
        payload.username,
        payload.password,
        email=payload.email,
        role=payload.role,
    )


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    actor: User = Depends(require_admin),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    return AuthService(database, settings).update_user(
        actor, user_id, payload.role, payload.is_active
    )


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: str,
    payload: AdminPasswordReset,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    return AuthService(database, settings).reset_password(user_id, payload.new_password)
