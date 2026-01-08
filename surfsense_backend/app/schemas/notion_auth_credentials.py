from datetime import UTC, datetime

from pydantic import BaseModel, field_validator


class NotionAuthCredentialsBase(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    expires_at: datetime | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    workspace_icon: str | None = None
    bot_id: str | None = None

    @property
    def is_expired(self) -> bool:
        """Check if the credentials have expired."""
        if self.expires_at is None:
            return False  # Long-lived token, treat as not expired
        return self.expires_at <= datetime.now(UTC)

    @property
    def is_refreshable(self) -> bool:
        """Check if the credentials can be refreshed."""
        return self.refresh_token is not None

    def to_dict(self) -> dict:
        """Convert credentials to dictionary for storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "workspace_icon": self.workspace_icon,
            "bot_id": self.bot_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NotionAuthCredentialsBase":
        """Create credentials from dictionary."""
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])

        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in"),
            expires_at=expires_at,
            workspace_id=data.get("workspace_id"),
            workspace_name=data.get("workspace_name"),
            workspace_icon=data.get("workspace_icon"),
            bot_id=data.get("bot_id"),
        )

    @field_validator("expires_at", mode="before")
    @classmethod
    def ensure_aware_utc(cls, v):
        # Strings like "2025-08-26T14:46:57.367184"
        if isinstance(v, str):
            # add +00:00 if missing tz info
            if v.endswith("Z"):
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            dt = datetime.fromisoformat(v)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        # datetime objects
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=UTC)
        return v
