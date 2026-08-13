"""What a generator's delivery step returns, per door kind."""

from __future__ import annotations

from dataclasses import dataclass

from app.artifacts.schemas.saved import ArtifactSaved


@dataclass(frozen=True)
class ArtifactRef:
    """A persisted artifact (authenticated doors). Carries what the agent
    receipt and the REST response both need without re-reading the DB."""

    saved: ArtifactSaved
    workspace_id: int
    revised_prompt: str | None = None


@dataclass(frozen=True)
class GeneratedBytes:
    """Raw output for the no-persist public door."""

    data: bytes
    mime_type: str
    ext: str


GenerationResult = ArtifactRef | GeneratedBytes
