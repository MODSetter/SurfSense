"""Microsoft OneDrive OAuth credentials schema."""

from datetime import UTC, datetime

from pydantic import BaseModel, field_validator


class OneDriveAuthCredentialsBase(BaseModel):
    """Microsoft OneDrive OAuth credentials."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None
    expires_at: datetime | None = None
    scope: str | None = None
    user_email: str | None = None
    user_name: str | None = None
    tenant_id: str | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at <= datetime.now(UTC)

    @property
    def is_refreshable(self) -> bool:
        return self.refresh_token is not None

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "scope": self.scope,
            "user_email": self.user_email,
            "user_name": self.user_name,
            "tenant_id": self.tenant_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OneDriveAuthCredentialsBase":
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            expires_at=expires_at,
            scope=data.get("scope"),
            user_email=data.get("user_email"),
            user_name=data.get("user_name"),
            tenant_id=data.get("tenant_id"),
        )

    @field_validator("expires_at", mode="before")
    @classmethod
    def ensure_aware_utc(cls, v):
        if isinstance(v, str):
            if v.endswith("Z"):
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            dt = datetime.fromisoformat(v)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=UTC)
        return v
