from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.db import PersonalAccessToken, User

AuthMethod = Literal["session", "pat", "system"]


@dataclass(frozen=True)
class AuthContext:
    """Typed principal for authorization decisions."""

    user: User
    method: AuthMethod
    pat: PersonalAccessToken | None = None
    source: str | None = None

    @classmethod
    def session(cls, user: User) -> AuthContext:
        return cls(user=user, method="session")

    @classmethod
    def pat_auth(cls, user: User, pat: PersonalAccessToken) -> AuthContext:
        return cls(user=user, method="pat", pat=pat)

    @classmethod
    def system(cls, user: User, source: str) -> AuthContext:
        return cls(user=user, method="system", source=source)

    @property
    def is_gated(self) -> bool:
        return self.method == "pat"

    @property
    def is_session(self) -> bool:
        return self.method == "session"
