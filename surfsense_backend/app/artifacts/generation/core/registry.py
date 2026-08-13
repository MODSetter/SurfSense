"""The generator registry: one entry per artifact kind, read by every door.

Mirrors the capability registry (``app/capabilities/core/store.py``): the agent
tool door, the authenticated REST door, and the public funnel door all iterate
this list, so adding a kind is a single ``register()`` — no door edits.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langgraph.types import Command
    from pydantic import BaseModel
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.artifacts.generation.core.result import ArtifactRef, GeneratedBytes
    from app.db import Workspace


@dataclass(frozen=True)
class PublicArtifactTool:
    """SEO metadata for a publicly reachable generator (landing pages)."""

    title: str
    description: str
    seo_slug: str


class ArtifactGenerator(ABC):
    """One artifact kind. Static identity + the kind-specific steps the generic
    pipeline calls; the doors supply the context (authenticated vs anonymous)."""

    kind: str
    usage_type: str
    tool_name: str
    tool_description: str
    receipt_type: str
    receipt_route: str = "deliverables"
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    # None => not exposed on the public funnel door.
    seo: PublicArtifactTool | None = None
    # Exception types whose message is safe to surface verbatim (e.g. "no model
    # configured"); doors show these to the caller instead of a generic 500.
    user_facing_errors: tuple[type[Exception], ...] = ()

    @abstractmethod
    async def resolve_workspace(
        self, session: AsyncSession, workspace: Workspace, override: int | None
    ) -> Any: ...

    @abstractmethod
    def resolve_anonymous(self) -> Any: ...

    @abstractmethod
    async def billing(
        self, session: AsyncSession, model: Any, workspace: Workspace
    ) -> tuple[str, str, int]: ...

    @abstractmethod
    async def run(self, model: Any, req: BaseModel) -> dict: ...

    @abstractmethod
    async def persist(
        self,
        session: AsyncSession,
        *,
        workspace_id: int,
        req: BaseModel,
        model: Any,
        response: dict,
        thread_id: int | None,
        tool_call_id: str | None,
        committed_by_turn: bool,
    ) -> ArtifactRef: ...

    @abstractmethod
    async def to_bytes(self, response: dict) -> GeneratedBytes: ...

    @abstractmethod
    def render_success(
        self, ref: ArtifactRef, req: BaseModel, tool_call_id: str
    ) -> Command: ...

    @abstractmethod
    def rest_response(self, ref: ArtifactRef) -> BaseModel: ...

    def preview(self, req: BaseModel) -> str | None:
        return None

    def audit(self, req: BaseModel) -> dict:
        return {}


_REGISTRY: dict[str, ArtifactGenerator] = {}
_LOADED = False


def register(generator: ArtifactGenerator) -> None:
    _REGISTRY[generator.kind] = generator


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    # Import builtin generators for their register() side effect. Kept lazy so
    # the registry module has no import-time dependency on any kind.
    from app.artifacts.generation.image import generator as _image  # noqa: F401


def all_generators() -> list[ArtifactGenerator]:
    _ensure_loaded()
    return list(_REGISTRY.values())


def get_generator(kind: str) -> ArtifactGenerator | None:
    _ensure_loaded()
    return _REGISTRY.get(kind)


def public_generators() -> list[ArtifactGenerator]:
    return [g for g in all_generators() if g.seo is not None]
