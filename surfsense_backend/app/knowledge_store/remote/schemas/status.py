"""A connected remote as the UI may see it — no secrets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.knowledge_store.remote.schemas.spec import RemoteProviderName


@dataclass(frozen=True)
class RemoteStatus:
    """One attached destination."""

    provider: RemoteProviderName
    url: str
    branch: str
    last_pushed_revision: str | None
    last_pushed_at: datetime | None
    last_push_error: str | None
