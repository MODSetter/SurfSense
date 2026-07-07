"""Active-workspace state and natural-language resolution of a workspace.

Every workspace-scoped tool takes a workspace by name or id, or omits it to use
the active one. This keeps ids out of the conversation: the model (or user)
speaks a name, we resolve it, and remember the choice for later calls.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field

from .auth.identity import current_identity
from .client import SurfSenseClient
from .errors import ToolError
from .workspace_matching import as_int, match_by_name, name_list

# ponytail: one small entry per distinct caller (API token). Bounded so a flood
# of keys can't grow memory without limit; an evicted caller just re-resolves
# its default workspace on the next call. Upgrade path: a TTL/LRU store if
# per-caller state ever grows past this one field.
_MAX_TRACKED_IDENTITIES = 2048

# Shared parameter type for every workspace-scoped tool.
WorkspaceParam = Annotated[
    str | None,
    Field(
        description="Workspace name or id, e.g. 'Research' or '3'. Omit to use "
        "the active workspace (set with surfsense_select_workspace)."
    ),
]


@dataclass(frozen=True)
class Workspace:
    """A SurfSense workspace (the product's "search space")."""

    id: int
    name: str
    description: str | None = None
    is_owner: bool = False
    member_count: int = 1


class WorkspaceContext:
    """Resolves workspace references and tracks the active selection."""

    def __init__(
        self, client: SurfSenseClient, *, preferred_reference: str | None = None
    ) -> None:
        self._client = client
        self._preferred_reference = preferred_reference
        # Active selection is per caller: one shared slot would leak one user's
        # choice to every other user on a shared server.
        self._active_by_identity: OrderedDict[str, Workspace] = OrderedDict()

    @property
    def active(self) -> Workspace | None:
        return self._active_by_identity.get(current_identity())

    def remember(self, workspace: Workspace) -> Workspace:
        """Make ``workspace`` the default for the current caller's later calls."""
        identity = current_identity()
        self._active_by_identity[identity] = workspace
        self._active_by_identity.move_to_end(identity)
        while len(self._active_by_identity) > _MAX_TRACKED_IDENTITIES:
            self._active_by_identity.popitem(last=False)
        return workspace

    async def fetch_all(self) -> list[Workspace]:
        """List every workspace the token can access."""
        rows = await self._client.request("GET", "/workspaces")
        return [_to_workspace(row) for row in rows or []]

    async def resolve(self, reference: str | int | None) -> Workspace:
        """Resolve a name/id (or the active/preferred default) to a workspace."""
        if reference is None or (isinstance(reference, str) and not reference.strip()):
            return await self._resolve_default()
        return self.remember(await self._match(reference))

    async def _resolve_default(self) -> Workspace:
        active = self.active
        if active is not None:
            return active
        if self._preferred_reference:
            return self.remember(await self._match(self._preferred_reference))
        return self.remember(await self._only_workspace_or_prompt())

    async def _only_workspace_or_prompt(self) -> Workspace:
        workspaces = await self.fetch_all()
        if len(workspaces) == 1:
            return workspaces[0]
        if not workspaces:
            raise ToolError(
                "No accessible workspaces. Confirm the token's account has a "
                "workspace with API access enabled."
            )
        raise ToolError(
            "No workspace selected. Choose one first with surfsense_select_workspace, "
            f"or pass 'workspace'. Available: {name_list(workspaces)}."
        )

    async def _match(self, reference: str | int) -> Workspace:
        workspaces = await self.fetch_all()
        as_id = as_int(reference)
        if as_id is not None:
            found = next((w for w in workspaces if w.id == as_id), None)
            if found is None:
                raise ToolError(
                    f"No workspace with id {as_id}. Available: {name_list(workspaces)}."
                )
            return found
        return match_by_name(str(reference), workspaces)


def _to_workspace(row: dict) -> Workspace:
    return Workspace(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        is_owner=row.get("is_owner", False),
        member_count=row.get("member_count", 1),
    )
