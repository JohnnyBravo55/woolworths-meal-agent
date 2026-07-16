"""Simple user auth for hosted multi-user deployments (Phase 2)."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

PROJECT_ROOT = Path(__file__).resolve().parents[4]
USERS_FILE = PROJECT_ROOT / "data" / "users.json"
USER_STATE_ROOT = PROJECT_ROOT / "data" / "woolworths_sessions"


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    token: str
    is_subscriber: bool = False


class UserStore:
    def __init__(self) -> None:
        self._lock = Lock()
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        USER_STATE_ROOT.mkdir(parents=True, exist_ok=True)
        if not USERS_FILE.exists():
            USERS_FILE.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, dict]:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, dict]) -> None:
        USERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()

    def register(self, email: str, password: str) -> User:
        email = email.strip().lower()
        with self._lock:
            data = self._load()
            if email in data:
                raise ValueError("Email already registered")
            user_id = str(uuid.uuid4())
            salt = secrets.token_hex(8)
            token = secrets.token_urlsafe(32)
            user = User(
                id=user_id,
                email=email,
                password_hash=self._hash_password(password, salt),
                token=token,
            )
            data[email] = {
                "id": user_id,
                "email": email,
                "salt": salt,
                "password_hash": user.password_hash,
                "token": token,
                "is_subscriber": False,
            }
            self._save(data)
            (USER_STATE_ROOT / user_id).mkdir(parents=True, exist_ok=True)
            return user

    def login(self, email: str, password: str) -> User:
        email = email.strip().lower()
        with self._lock:
            data = self._load()
            row = data.get(email)
            if not row:
                raise ValueError("Invalid email or password")
            expected = self._hash_password(password, row["salt"])
            if expected != row["password_hash"]:
                raise ValueError("Invalid email or password")
            return User(
                id=row["id"],
                email=row["email"],
                password_hash=row["password_hash"],
                token=row["token"],
                is_subscriber=bool(row.get("is_subscriber")),
            )

    def get_by_token(self, token: str) -> User | None:
        if not token:
            return None
        data = self._load()
        for row in data.values():
            if row.get("token") == token:
                return User(
                    id=row["id"],
                    email=row["email"],
                    password_hash=row["password_hash"],
                    token=row["token"],
                    is_subscriber=bool(row.get("is_subscriber")),
                )
        return None

    def woolworths_state_dir(self, user_id: str) -> Path:
        return USER_STATE_ROOT / user_id


user_store = UserStore()
