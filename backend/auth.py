from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
import jwt
from jwt import InvalidTokenError
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .models import RefreshToken, User, utc_now


USER_ID_PATTERN = re.compile(r"[^a-zA-Z0-9_.:@-]+")
PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("not-a-real-password-9d2d7b")


@dataclass(frozen=True)
class UserContext:
    owner_id: str
    username: str
    role: str


def normalize_owner_id(value: str | None) -> str:
    normalized = USER_ID_PATTERN.sub("-", (value or "local").strip())[:64].strip("-")
    return normalized or "local"


def _http_error(code: int, detail: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if code == status.HTTP_401_UNAUTHORIZED else None
    return HTTPException(status_code=code, detail=detail, headers=headers)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def validate_password(password: str) -> None:
    categories = sum(
        (
            any(character.islower() for character in password),
            any(character.isupper() for character in password),
            any(character.isdigit() for character in password),
            any(not character.isalnum() for character in password),
        )
    )
    if len(password) < 10 or categories < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="密码至少 10 位，并至少包含大写字母、小写字母、数字、特殊字符中的三类",
        )


class AuthService:
    def __init__(self, database: Session, settings: Settings | None = None):
        self.database = database
        self.settings = settings or get_settings()

    def register(self, username: str, password: str, email: str | None = None) -> User:
        self._ensure_enabled()
        if not self.settings.auth_registration_enabled:
            raise HTTPException(status_code=403, detail="当前未开放注册")
        return self.create_user(username, password, email=email, role="user")

    def create_user(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
        role: str = "user",
    ) -> User:
        validate_password(password)
        username = username.strip().lower()
        email = (email or "").strip().lower() or None
        duplicate = self.database.scalar(
            select(User).where(or_(User.username == username, User.email == email))
            if email
            else select(User).where(User.username == username)
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="用户名或邮箱已被使用")
        user = User(
            username=username,
            email=email,
            password_hash=PASSWORD_HASHER.hash(password),
            role=role,
        )
        self.database.add(user)
        try:
            self.database.commit()
        except IntegrityError as exc:
            self.database.rollback()
            raise HTTPException(status_code=409, detail="用户名或邮箱已被使用") from exc
        self.database.refresh(user)
        return user

    def login(self, username: str, password: str) -> User:
        self._ensure_enabled()
        user = self.database.scalar(
            select(User).where(User.username == username.strip().lower())
        )
        encoded = user.password_hash if user else DUMMY_PASSWORD_HASH
        try:
            valid = PASSWORD_HASHER.verify(encoded, password)
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        if not user or not valid:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已停用")
        if PASSWORD_HASHER.check_needs_rehash(user.password_hash):
            user.password_hash = PASSWORD_HASHER.hash(password)
        user.last_login_at = utc_now()
        self.database.commit()
        self.database.refresh(user)
        return user

    def issue_token_pair(
        self,
        user: User,
        *,
        commit: bool = True,
    ) -> tuple[str, str, int]:
        now = utc_now()
        access_expires = now + timedelta(minutes=self.settings.jwt_access_minutes)
        refresh_expires = now + timedelta(days=self.settings.jwt_refresh_days)
        access_id = str(uuid.uuid4())
        refresh_id = str(uuid.uuid4())
        common = {
            "sub": user.id,
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "iat": now,
            "nbf": now,
            "ver": user.token_version,
        }
        access_token = jwt.encode(
            {
                **common,
                "jti": access_id,
                "typ": "access",
                "exp": access_expires,
                "role": user.role,
                "username": user.username,
            },
            self.settings.jwt_secret,
            algorithm="HS256",
        )
        refresh_token = jwt.encode(
            {
                **common,
                "jti": refresh_id,
                "typ": "refresh",
                "exp": refresh_expires,
            },
            self.settings.jwt_secret,
            algorithm="HS256",
        )
        self.database.execute(
            delete(RefreshToken)
            .where(RefreshToken.expires_at <= now)
            .execution_options(synchronize_session=False)
        )
        self.database.add(
            RefreshToken(
                id=refresh_id,
                user_id=user.id,
                token_hash=self._token_hash(refresh_token),
                expires_at=refresh_expires,
            )
        )
        if commit:
            self.database.commit()
        return access_token, refresh_token, self.settings.jwt_access_minutes * 60

    def rotate_refresh_token(self, raw_token: str) -> tuple[User, str, str, int]:
        self._ensure_enabled()
        claims = self._decode_token(raw_token, "refresh")
        token = self.database.scalar(
            select(RefreshToken)
            .where(RefreshToken.id == claims["jti"])
            .with_for_update()
        )
        user = self.database.get(User, claims["sub"])
        token_matches = token and hmac.compare_digest(
            token.token_hash, self._token_hash(raw_token)
        )
        if not token or not token_matches or not user:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, "刷新令牌无效")
        if token.revoked_at is not None:
            self.revoke_all(user)
            raise _http_error(status.HTTP_401_UNAUTHORIZED, "刷新令牌已被使用，请重新登录")
        if _utc(token.expires_at) <= utc_now() or claims.get("ver") != user.token_version:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, "刷新令牌已过期")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已停用")

        token.revoked_at = utc_now()
        access_token, refresh_token, expires_in = self.issue_token_pair(user, commit=False)
        replacement_claims = self._decode_token(refresh_token, "refresh")
        token.replaced_by_id = replacement_claims["jti"]
        self.database.commit()
        return user, access_token, refresh_token, expires_in

    def authenticate_access_token(self, raw_token: str) -> User:
        claims = self._decode_token(raw_token, "access")
        user = self.database.get(User, claims["sub"])
        if not user or claims.get("ver") != user.token_version:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, "登录状态已失效")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已停用")
        return user

    def logout(self, raw_token: str) -> None:
        try:
            claims = self._decode_token(raw_token, "refresh")
        except HTTPException:
            return
        token = self.database.get(RefreshToken, claims["jti"])
        if token and token.revoked_at is None:
            token.revoked_at = utc_now()
            self.database.commit()

    def revoke_all(self, user: User, *, bump_version: bool = True) -> None:
        now = utc_now()
        self.database.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        if bump_version:
            user.token_version += 1
        self.database.commit()

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        try:
            valid = PASSWORD_HASHER.verify(user.password_hash, current_password)
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        if not valid:
            raise HTTPException(status_code=400, detail="当前密码不正确")
        validate_password(new_password)
        user.password_hash = PASSWORD_HASHER.hash(new_password)
        self.revoke_all(user)

    def list_users(self) -> list[User]:
        return list(self.database.scalars(select(User).order_by(User.created_at.desc())))

    def update_user(self, actor: User, user_id: str, role: str | None, is_active: bool | None) -> User:
        user = self.database.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="账号不存在")
        if actor.id == user.id and (role == "user" or is_active is False):
            raise HTTPException(status_code=400, detail="不能降低或停用当前登录的管理员账号")
        removes_admin = user.role == "admin" and (
            role == "user" or is_active is False
        )
        if removes_admin:
            active_admin_ids = list(
                self.database.scalars(
                    select(User.id)
                    .where(User.role == "admin", User.is_active.is_(True))
                    .order_by(User.id)
                    .with_for_update()
                )
            )
            if len(active_admin_ids) <= 1:
                raise HTTPException(status_code=400, detail="系统必须保留至少一个启用的管理员")
        changed = False
        if role is not None and role != user.role:
            user.role = role
            changed = True
        if is_active is not None and is_active != user.is_active:
            user.is_active = is_active
            changed = True
        if changed:
            self.revoke_all(user)
        else:
            self.database.refresh(user)
        return user

    def reset_password(self, user_id: str, new_password: str) -> User:
        user = self.database.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="账号不存在")
        validate_password(new_password)
        user.password_hash = PASSWORD_HASHER.hash(new_password)
        self.revoke_all(user)
        return user

    def bootstrap_admin(self) -> User | None:
        username = self.settings.bootstrap_admin_username.strip().lower()
        password = self.settings.bootstrap_admin_password
        if not username:
            return None
        user = self.database.scalar(select(User).where(User.username == username))
        if user:
            if user.role != "admin":
                raise RuntimeError("Bootstrap admin username already belongs to a non-admin account")
            return user
        return self.create_user(username, password, role="admin")

    def _decode_token(self, token: str, expected_type: str) -> dict:
        try:
            claims = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=["HS256"],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={"require": ["exp", "iat", "nbf", "sub", "jti", "typ"]},
            )
        except InvalidTokenError as exc:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, "令牌无效或已过期") from exc
        if claims.get("typ") != expected_type:
            raise _http_error(status.HTTP_401_UNAUTHORIZED, "令牌类型无效")
        return claims

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _ensure_enabled(self) -> None:
        if not self.settings.auth_enabled:
            raise HTTPException(status_code=404, detail="账号系统未启用")


def _bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _http_error(status.HTTP_401_UNAUTHORIZED, "请先登录")
    return token.strip()


def resolve_user_context(
    request: Request,
    fallback_client_id: str | None = None,
    database: Session | None = None,
    settings: Settings | None = None,
) -> UserContext:
    settings = settings or get_settings()
    if not settings.auth_enabled:
        owner_id = normalize_owner_id(fallback_client_id)
        return UserContext(owner_id=owner_id, username=owner_id, role="admin")
    if database is None:
        raise RuntimeError("Database session is required when authentication is enabled")
    user = AuthService(database, settings).authenticate_access_token(_bearer_token(request))
    return UserContext(owner_id=user.id, username=user.username, role=user.role)


def get_authenticated_user(
    request: Request,
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="账号系统未启用")
    return AuthService(database, settings).authenticate_access_token(_bearer_token(request))


def require_admin(user: User = Depends(get_authenticated_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
