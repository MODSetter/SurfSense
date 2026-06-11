"""Content-addressed cache for synthesised segments.

Each segment's audio is keyed by everything that determines its bytes (voice,
language, speed, text). Keeping the cache in a stable per-podcast directory
makes re-renders cheap: changing one speaker's voice only misses that speaker's
turns, and a worker restart mid-render resumes from whatever was already
written. The key intentionally excludes the segment's position so identical
lines (e.g. repeated "Right.") synthesise once.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.podcasts.tts import SynthesisRequest


class SegmentCache:
    """On-disk store of segment audio, addressed by request content hash."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def key(self, request: SynthesisRequest) -> str:
        """A stable hash of the inputs that determine the synthesised bytes."""
        material = json.dumps(
            {
                "voice": request.voice,
                "language": request.language,
                "speed": request.speed,
                "text": request.text,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def path(self, key: str, container: str) -> Path:
        return self._root / f"{key}.{container}"

    def get(self, key: str, container: str) -> Path | None:
        """Return the cached segment path, or ``None`` on a miss."""
        path = self.path(key, container)
        return path if path.exists() else None

    def put(self, key: str, container: str, data: bytes) -> Path:
        """Write ``data`` for ``key`` and return its path."""
        path = self.path(key, container)
        path.write_bytes(data)
        return path
