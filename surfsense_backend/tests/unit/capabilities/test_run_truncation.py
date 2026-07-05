"""Tool-boundary truncation + run read-tool behavior (no DB).

Covers the pure pieces of the DB-backed run log: JSONL serialization, the
char-budgeted preview (including the single-oversized-item case and the
storage-failure degrade), and the ``read_run``/``search_run`` tools' paging,
search, ReDoS fallback, and workspace scoping — all with a fake session so the
unit suite never touches a database.
"""

from __future__ import annotations

import contextlib
import json

import pytest
from pydantic import BaseModel

from app.agents.chat.multi_agent_chat.subagents.shared import run_reader
from app.capabilities.core.access.agent import _build_preview
from app.capabilities.core.runs import (
    RUN_OUTPUT_CHAR_CAP,
    SerializedOutput,
    serialize_output,
)

pytestmark = pytest.mark.unit


class _Item(BaseModel):
    id: int
    name: str
    note: str | None = None


class _Output(BaseModel):
    items: list[_Item]


class _Scalar(BaseModel):
    value: str


def test_serialize_output_is_jsonl_and_excludes_none():
    out = _Output(items=[_Item(id=1, name="a"), _Item(id=2, name="b", note="x")])
    result = serialize_output(out)

    lines = result.text.split("\n")
    assert result.item_count == 2
    assert len(lines) == 2
    # exclude_none: the first item has no "note" key
    assert "note" not in json.loads(lines[0])
    assert json.loads(lines[1])["note"] == "x"
    assert result.char_count == len(result.text)


def test_serialize_output_without_items_is_single_line():
    result = serialize_output(_Scalar(value="hi"))
    assert result.item_count == 1
    assert json.loads(result.text) == {"value": "hi"}


def test_preview_is_char_budgeted_and_references_run():
    # Many small items whose total blows the cap.
    per_item = "y" * 500
    items = [f'{{"i": {i}, "v": "{per_item}"}}' for i in range(500)]
    body = "\n".join(items)
    serialized = SerializedOutput(text=body, item_count=len(items), char_count=len(body))

    preview = _build_preview(serialized, run_id="abc")

    assert len(preview) < serialized.char_count
    assert "run_abc" in preview
    assert "read_run" in preview
    # Only a prefix of items is shown.
    assert preview.count('"i":') < len(items)


def test_preview_handles_single_oversized_item():
    huge = "z" * (RUN_OUTPUT_CHAR_CAP * 2)
    serialized = SerializedOutput(text=huge, item_count=1, char_count=len(huge))

    preview = _build_preview(serialized, run_id="big")

    # Still returns a clipped head rather than nothing.
    assert "z" in preview
    assert "run_big" in preview
    assert len(preview) < serialized.char_count


def test_preview_degrades_when_storage_failed():
    body = "\n".join(f'{{"i": {i}}}' for i in range(200))
    serialized = SerializedOutput(text=body, item_count=200, char_count=len(body))

    preview = _build_preview(serialized, run_id=None)

    assert "storage error" in preview
    assert "run_" not in preview


# --- read tools -----------------------------------------------------------


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, value, calls):
        self._value = value
        self._calls = calls

    async def execute(self, stmt):
        self._calls.append(str(stmt))
        return _FakeResult(self._value)


def _patch_session(monkeypatch, value, calls):
    @contextlib.asynccontextmanager
    async def _maker():
        yield _FakeSession(value, calls)

    monkeypatch.setattr(run_reader, "shielded_async_session", _maker)


def _tools():
    read_run, search_run = run_reader.build_run_reader_tools(workspace_id=7)
    return read_run, search_run


_BODY = "\n".join(f'{{"i": {i}, "name": "item_{i}"}}' for i in range(10))


@pytest.mark.asyncio
async def test_read_run_paginates(monkeypatch):
    calls: list[str] = []
    _patch_session(monkeypatch, _BODY, calls)
    read_run, _ = _tools()

    out = await read_run.ainvoke(
        {"ref": "run_" + "0" * 8 + "-0000-0000-0000-000000000000",
         "offset": 2, "limit": 3}
    )
    assert "item_2" in out and "item_3" in out and "item_4" in out
    assert "item_0" not in out and "item_5" not in out
    # Scoped by workspace_id in the query.
    assert "workspace_id" in calls[0]


@pytest.mark.asyncio
async def test_read_run_rejects_bad_ref(monkeypatch):
    _patch_session(monkeypatch, _BODY, [])
    read_run, _ = _tools()
    out = await read_run.ainvoke({"ref": "not-a-ref"})
    assert "not a valid run reference" in out


@pytest.mark.asyncio
async def test_read_run_not_found(monkeypatch):
    _patch_session(monkeypatch, None, [])
    read_run, _ = _tools()
    out = await read_run.ainvoke(
        {"ref": "run_" + "0" * 8 + "-0000-0000-0000-000000000000"}
    )
    assert "not found" in out


@pytest.mark.asyncio
async def test_search_run_matches(monkeypatch):
    _patch_session(monkeypatch, _BODY, [])
    _, search_run = _tools()
    out = await search_run.ainvoke(
        {"ref": "spill_" + "0" * 8 + "-0000-0000-0000-000000000000",
         "pattern": "item_7"}
    )
    assert "item_7" in out
    assert "item_1" not in out.split("item_7")[0]


@pytest.mark.asyncio
async def test_search_run_falls_back_on_bad_regex(monkeypatch):
    _patch_session(monkeypatch, _BODY, [])
    _, search_run = _tools()
    # "(" is an invalid regex -> substring fallback, must not raise.
    out = await search_run.ainvoke(
        {"ref": "run_" + "0" * 8 + "-0000-0000-0000-000000000000", "pattern": "("}
    )
    assert "matched" in out or "No lines" in out
