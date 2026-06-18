"""Row projection handed to the eviction policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EvictionCandidate:
    id: int
    storage_key: str
    size_bytes: int
    last_used_at: datetime
    times_reused: int
