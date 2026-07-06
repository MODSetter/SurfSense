"""Workspace resolution: names, ids, defaults, and the ambiguous cases."""

from __future__ import annotations

import asyncio

import pytest

from surfsense_mcp.core.errors import ToolError
from surfsense_mcp.core.workspace_context import WorkspaceContext


class FakeClient:
    """Stands in for SurfSenseClient, serving a fixed workspace list."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def request(self, method: str, path: str, **_kwargs):
        assert (method, path) == ("GET", "/workspaces")
        return self._rows


def _rows(*names_ids: tuple[str, int]) -> list[dict]:
    return [{"id": wid, "name": name} for name, wid in names_ids]


def _context(rows: list[dict], preferred: str | None = None) -> WorkspaceContext:
    return WorkspaceContext(FakeClient(rows), preferred_reference=preferred)


def test_resolves_exact_name():
    ctx = _context(_rows(("Research", 1), ("Marketing", 2)))
    assert asyncio.run(ctx.resolve("Research")).id == 1


def test_resolves_case_insensitively():
    ctx = _context(_rows(("Research", 1)))
    assert asyncio.run(ctx.resolve("research")).id == 1


def test_resolves_unique_substring():
    ctx = _context(_rows(("Research Space", 1), ("Marketing", 2)))
    assert asyncio.run(ctx.resolve("resea")).id == 1


def test_ambiguous_substring_is_rejected():
    ctx = _context(_rows(("Research A", 1), ("Research B", 2)))
    with pytest.raises(ToolError):
        asyncio.run(ctx.resolve("research"))


def test_resolves_by_numeric_id():
    ctx = _context(_rows(("Research", 1), ("Marketing", 2)))
    assert asyncio.run(ctx.resolve(2)).name == "Marketing"
    assert asyncio.run(ctx.resolve("2")).name == "Marketing"


def test_unknown_id_is_rejected():
    ctx = _context(_rows(("Research", 1)))
    with pytest.raises(ToolError):
        asyncio.run(ctx.resolve(99))


def test_unknown_name_is_rejected():
    ctx = _context(_rows(("Research", 1)))
    with pytest.raises(ToolError):
        asyncio.run(ctx.resolve("Nope"))


def test_default_auto_selects_single_workspace():
    ctx = _context(_rows(("Only", 7)))
    assert asyncio.run(ctx.resolve(None)).id == 7


def test_default_with_multiple_requires_a_choice():
    ctx = _context(_rows(("A", 1), ("B", 2)))
    with pytest.raises(ToolError):
        asyncio.run(ctx.resolve(None))


def test_default_with_no_workspaces_is_rejected():
    ctx = _context([])
    with pytest.raises(ToolError):
        asyncio.run(ctx.resolve(None))


def test_default_uses_preferred_reference():
    ctx = _context(_rows(("A", 1), ("Research", 2)), preferred="Research")
    assert asyncio.run(ctx.resolve(None)).id == 2


def test_resolution_is_remembered_as_active():
    ctx = _context(_rows(("A", 1), ("B", 2)))
    asyncio.run(ctx.resolve("B"))
    assert ctx.active is not None and ctx.active.id == 2
    # a later default call reuses the active selection without re-choosing
    assert asyncio.run(ctx.resolve(None)).id == 2
