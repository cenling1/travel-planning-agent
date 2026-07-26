from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..auth import AuthService, get_authenticated_user
from ..config import Settings, get_settings
from ..database import get_db
from ..models import User
from ..schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)


router = APIRouter(prefix="/auth", tags=["auth"])


REFRESH_COOKIE_KEY = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_KEY,
        value=refresh_token,
        max_age=settings.jwt_refresh_days * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain or None,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_KEY,
        path=REFRESH_COOKIE_PATH,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain or None,
    )


def _token_pair_response(
    service: AuthService,
    user: User,
    response: Response,
    settings: Settings,
) -> TokenPair:
    access_token, refresh_token, expires_in = service.issue_token_pair(user)
    _set_refresh_cookie(response, refresh_token, settings)
    return TokenPair(
        access_token=access_token,
        expires_in=expires_in,
        user=user,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenPair:
    service = AuthService(database, settings)
    user = service.register(payload.username, payload.password, payload.email)
    return _token_pair_response(service, user, response, settings)


@router.post("/login", response_model=TokenPair)
def login(
    payload: LoginRequest,
    response: Response,
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenPair:
    service = AuthService(database, settings)
    return _token_pair_response(service, service.login(payload.username, payload.password), response, settings)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    response: Response,
    payload: RefreshRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_KEY),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenPair:
    # Prefer HttpOnly cookie, fall back to request body for backward compatibility
    raw_token = refresh_token_cookie or (payload.refresh_token if payload else None)
    if not raw_token:
        raise HTTPException(status_code=401, detail="缺少刷新令牌")

    user, access_token, refresh_token, expires_in = AuthService(
        database, settings
    ).rotate_refresh_token(raw_token)
    _set_refresh_cookie(response, refresh_token, settings)
    return TokenPair(
        access_token=access_token,
        expires_in=expires_in,
        user=user,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    payload: RefreshRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_KEY),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    raw_token = refresh_token_cookie or (payload.refresh_token if payload else None)
    if raw_token:
        AuthService(database, settings).logout(raw_token)
    _clear_refresh_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    response: Response,
    user: User = Depends(get_authenticated_user),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    AuthService(database, settings).revoke_all(user)
    _clear_refresh_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_authenticated_user)) -> UserOut:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_authenticated_user),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    AuthService(database, settings).change_password(
        user, payload.current_password, payload.new_password
    )
    _clear_refresh_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
