"""Active-workspace state and natural-language resolution of a workspace.

Every workspace-scoped tool takes a workspace by name or id, or omits it to use
the active one. This keeps ids out of the conversation: the model (or user)
speaks a name, we resolve it, and remember the choice for later calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from .client import SurfSenseClient
from .errors import ToolError


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
        self._active: Workspace | None = None

    @property
    def active(self) -> Workspace | None:
        return self._active

    def remember(self, workspace: Workspace) -> Workspace:
        """Make ``workspace`` the default for later scoped calls."""
        self._active = workspace
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
        if self._active is not None:
            return self._active
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
            f"or pass 'workspace'. Available: {_name_list(workspaces)}."
        )

    async def _match(self, reference: str | int) -> Workspace:
        workspaces = await self.fetch_all()
        as_id = _as_int(reference)
        if as_id is not None:
            found = next((w for w in workspaces if w.id == as_id), None)
            if found is None:
                raise ToolError(
                    f"No workspace with id {as_id}. Available: {_name_list(workspaces)}."
                )
            return found
        return _match_by_name(str(reference), workspaces)


def _match_by_name(reference: str, workspaces: list[Workspace]) -> Workspace:
    """Match on name: exact, then case-insensitive, then unique substring."""
    needle = reference.strip()
    exact = [w for w in workspaces if w.name == needle]
    if exact:
        return exact[0]
    lowered = needle.casefold()
    insensitive = [w for w in workspaces if w.name.casefold() == lowered]
    if insensitive:
        return insensitive[0]
    partial = [w for w in workspaces if lowered in w.name.casefold()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise ToolError(
            f"'{reference}' matches several workspaces: {_name_list(partial)}. "
            "Use a more specific name or the id."
        )
    raise ToolError(
        f"No workspace named '{reference}'. Available: {_name_list(workspaces)}."
    )


def _to_workspace(row: dict) -> Workspace:
    return Workspace(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        is_owner=row.get("is_owner", False),
        member_count=row.get("member_count", 1),
    )


def _as_int(reference: str | int) -> int | None:
    if isinstance(reference, int):
        return reference
    text = reference.strip()
    return int(text) if text.isdigit() else None


def _name_list(workspaces: list[Workspace]) -> str:
    return ", ".join(f"{w.name} (id {w.id})" for w in workspaces)
