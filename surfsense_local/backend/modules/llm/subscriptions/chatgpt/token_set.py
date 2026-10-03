import json
import time
from dataclasses import asdict, dataclass, replace

# Refresh this long before expiry, so a stream started on the token outlives it.
REFRESH_EARLY_SECONDS = 300


@dataclass(frozen=True)
class TokenSet:
    """One signed-in ChatGPT account, as stored encrypted on its connection."""

    client_id: str
    access_token: str
    refresh_token: str
    id_token: str
    expires_at: float
    account: str
    email: str | None = None
    # OpenAI may ask that a refresh wait until then.
    earliest_refresh_at: float | None = None

    def due(self, now: float | None = None) -> bool:
        """Whether this token should be refreshed before it is used."""
        now = time.time() if now is None else now
        if self.earliest_refresh_at is not None and now < self.earliest_refresh_at:
            return False
        return now >= self.expires_at - REFRESH_EARLY_SECONDS

    def refreshed(self, reply: dict, now: float | None = None) -> "TokenSet":
        """This account after a token response; fields the response omits are kept."""
        now = time.time() if now is None else now
        return replace(
            self,
            access_token=reply["access_token"],
            refresh_token=reply.get("refresh_token") or self.refresh_token,
            id_token=reply.get("id_token") or self.id_token,
            expires_at=now + float(reply.get("expires_in") or 3600),
            earliest_refresh_at=_earliest(reply),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "TokenSet":
        return cls(**json.loads(raw))


def _earliest(reply: dict) -> float | None:
    value = reply.get("earliest_refresh_at")
    return float(value) if isinstance(value, (int, float)) else None
