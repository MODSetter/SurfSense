from datetime import UTC, datetime

from pydantic import BaseModel


class GoogleAuthCredentialsBase(BaseModel):
    token: str
    refresh_token: str
    token_uri: str
    client_id: str
    expiry: datetime
    scopes: list[str]
    client_secret: str

    @property
    def expired(self) -> bool:
        """Check if the credentials have expired."""
        return self.expiry <= datetime.now(UTC)
