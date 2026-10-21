"""Local registration and login (no HTTP/JWT)."""

from __future__ import annotations

from pathlib import Path

import bcrypt
from sqlalchemy import select

from app.core.config import AppConfig
from app.core.database import Database
from app.core.exceptions import (
    AuthenticationError,
    UnauthorizedError,
    UserExistsError,
    ValidationError,
)
from app.models.user import User
from app.schemas.dtos import UserDTO
from app.utils.dates import ensure_naive_utc
from app.utils.strings import normalize_name


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except Exception:  # noqa: BLE001
        return False


def to_user_dto(user: User) -> UserDTO:
    return UserDTO(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


class AuthService:
    def __init__(self, database: Database, config: AppConfig | None = None) -> None:
        self.db = database
        self.config = config
        self._current_user_id: int | None = None

    def register(
        self,
        username: str,
        password: str,
        display_name: str | None = None,
        *,
        auto_login: bool = True,
    ) -> UserDTO:
        cleaned = (username or "").strip()
        if len(cleaned) < 3:
            raise ValidationError("Username must be at least 3 characters")
        if len(password or "") < 6:
            raise ValidationError("Password must be at least 6 characters")
        normalized = normalize_name(cleaned)
        with self.db.session_scope() as session:
            existing = session.scalar(
                select(User).where(User.normalized_username == normalized)
            )
            if existing is not None:
                raise UserExistsError(f"Username '{cleaned}' is already taken")
            user = User(
                username=cleaned,
                normalized_username=normalized,
                password_hash=hash_password(password),
                display_name=(display_name or cleaned).strip() or cleaned,
            )
            session.add(user)
            session.flush()
            dto = to_user_dto(user)
            uid = user.id
        if auto_login:
            self._current_user_id = uid
            self._remember_username(cleaned)
        return dto

    def login(self, username: str, password: str) -> UserDTO:
        cleaned = (username or "").strip()
        normalized = normalize_name(cleaned)
        with self.db.session_scope() as session:
            user = session.scalar(
                select(User).where(User.normalized_username == normalized)
            )
            if user is None or not verify_password(password, user.password_hash):
                raise AuthenticationError()
            user.last_login_at = ensure_naive_utc()
            session.flush()
            dto = to_user_dto(user)
            self._current_user_id = user.id
        self._remember_username(cleaned)
        return dto

    def logout(self) -> None:
        self._current_user_id = None

    def current_user(self) -> UserDTO | None:
        if self._current_user_id is None:
            return None
        with self.db.session_scope() as session:
            user = session.get(User, self._current_user_id)
            if user is None:
                self._current_user_id = None
                return None
            return to_user_dto(user)

    def require_user(self) -> UserDTO:
        user = self.current_user()
        if user is None:
            raise UnauthorizedError()
        return user

    def require_user_id(self) -> int:
        return self.require_user().id

    def change_password(self, old_password: str, new_password: str) -> None:
        if len(new_password or "") < 6:
            raise ValidationError("Password must be at least 6 characters")
        uid = self.require_user_id()
        with self.db.session_scope() as session:
            user = session.get(User, uid)
            if user is None:
                raise UnauthorizedError()
            if not verify_password(old_password, user.password_hash):
                raise AuthenticationError("Current password is incorrect")
            user.password_hash = hash_password(new_password)

    def list_usernames(self) -> list[str]:
        with self.db.session_scope() as session:
            rows = session.scalars(select(User.username).order_by(User.username)).all()
            return list(rows)

    def last_username(self) -> str | None:
        path = self._last_user_path()
        if path is None or not path.exists():
            return None
        try:
            value = path.read_text(encoding="utf-8").strip()
            return value or None
        except OSError:
            return None

    def _remember_username(self, username: str) -> None:
        path = self._last_user_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(username, encoding="utf-8")
        except OSError:
            pass

    def _last_user_path(self) -> Path | None:
        if self.config is None:
            return None
        return self.config.data_dir / "last_user.txt"
