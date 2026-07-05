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
    read_run, search_run, _export_run = run_reader.build_run_reader_tools(
        workspace_id=7
    )
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
async def test_read_run_char_offset_pages_inside_one_huge_item(monkeypatch):
    """A single item bigger than the cap is fully reachable via char_offset."""
    huge_line = "A" * RUN_OUTPUT_CHAR_CAP + "MARKER" + "B" * 1000
    _patch_session(monkeypatch, huge_line, [])
    read_run, _ = _tools()
    ref = "run_" + "0" * 8 + "-0000-0000-0000-000000000000"

    first = await read_run.ainvoke({"ref": ref, "offset": 0, "limit": 1})
    assert "MARKER" not in first  # clipped at the cap
    assert f"char_offset={RUN_OUTPUT_CHAR_CAP}" in first  # continuation hint

    second = await read_run.ainvoke(
        {"ref": ref, "offset": 0, "limit": 1, "char_offset": RUN_OUTPUT_CHAR_CAP}
    )
    assert "MARKER" in second
    assert "truncated" not in second  # remainder fits

    past_end = await read_run.ainvoke(
        {"ref": ref, "offset": 0, "limit": 1, "char_offset": len(huge_line) + 5}
    )
    assert "No content at char_offset" in past_end


@pytest.mark.asyncio
async def test_search_run_excerpts_huge_matched_line(monkeypatch):
    """A match inside a huge line returns a window around it, not the whole line."""
    huge_line = "x" * 100_000 + "NEEDLE" + "y" * 100_000
    _patch_session(monkeypatch, huge_line, [])
    _, search_run = _tools()

    out = await search_run.ainvoke(
        {"ref": "run_" + "0" * 8 + "-0000-0000-0000-000000000000",
         "pattern": "NEEDLE"}
    )
    assert "NEEDLE" in out
    assert "match at char 100000" in out
    assert len(out) < 2000  # excerpt, not the 200k line


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


# --- export_run ------------------------------------------------------------


_CRAWL_BODY = "\n".join(
    [
        json.dumps(
            {
                "url": "https://x.com/team/",
                "status": "success",
                "links": [
                    {"url": "https://x.com/author/jane/", "text": "Jane Doe",
                     "context": "Jane Doe General Partner", "kind": "internal"},
                    {"url": "https://x.com/author/bob/", "text": "Bob Roe",
                     "context": "Bob Roe Operations", "kind": "internal"},
                    # Duplicate of Jane (nav + card) — must dedupe.
                    {"url": "https://x.com/author/jane/", "text": "Jane Doe",
                     "context": "Jane Doe General Partner", "kind": "internal"},
                    {"url": "https://x.com/about/", "text": "About", "kind": "internal"},
                ],
            }
        ),
        json.dumps({"url": "https://x.com/jobs/", "status": "failed", "links": []}),
        "not json — skipped",
    ]
)


def test_rows_from_body_links_explode_and_items():
    links = run_reader._rows_from_body(_CRAWL_BODY, "links")
    assert len(links) == 4
    assert links[0]["page"] == "https://x.com/team/"
    assert links[0]["text"] == "Jane Doe"

    items = run_reader._rows_from_body(_CRAWL_BODY, "items")
    assert [i["url"] for i in items] == ["https://x.com/team/", "https://x.com/jobs/"]


def test_rows_to_csv_dedupes_and_orders_columns():
    records = run_reader._rows_from_body(_CRAWL_BODY, "links")
    csv_text, count = run_reader._rows_to_csv(records, ["page", "url", "text"])
    lines = csv_text.strip().split("\n")
    assert lines[0] == "page,url,text"
    assert count == 3  # 4 records - 1 duplicate
    assert len(lines) == 4  # header + 3 rows
    assert "Jane Doe" in lines[1]


@pytest.mark.asyncio
async def test_export_run_filters_and_saves(monkeypatch):
    _patch_session(monkeypatch, _CRAWL_BODY, [])
    saved: dict = {}

    async def _fake_save(*, virtual_path, content, workspace_id):
        saved["path"] = virtual_path
        saved["content"] = content
        saved["workspace_id"] = workspace_id
        return 42, "/documents/exports/team.csv"

    monkeypatch.setattr(run_reader, "_save_export_document", _fake_save)
    _, _, export_run = run_reader.build_run_reader_tools(workspace_id=7)

    out = await export_run.ainvoke(
        {
            "ref": "run_" + "0" * 8 + "-0000-0000-0000-000000000000",
            "path": "exports/team.csv",
            "rows": "links",
            "include_pattern": "/author/",
        }
    )
    assert "Exported 2 rows" in out  # Jane + Bob; About filtered; dupe deduped
    assert "/documents/exports/team.csv" in out
    assert "document id 42" in out
    assert saved["workspace_id"] == 7
    assert "About" not in saved["content"]
    assert "Bob Roe" in saved["content"]


@pytest.mark.asyncio
async def test_export_run_empty_filter_is_error(monkeypatch):
    _patch_session(monkeypatch, _CRAWL_BODY, [])
    _, _, export_run = run_reader.build_run_reader_tools(workspace_id=7)
    out = await export_run.ainvoke(
        {
            "ref": "run_" + "0" * 8 + "-0000-0000-0000-000000000000",
            "path": "exports/none.csv",
            "include_pattern": "no-such-thing-anywhere",
        }
    )
    assert out.startswith("Error: no rows to export")


@pytest.mark.asyncio
async def test_search_run_falls_back_on_bad_regex(monkeypatch):
    _patch_session(monkeypatch, _BODY, [])
    _, search_run = _tools()
    # "(" is an invalid regex -> substring fallback, must not raise.
    out = await search_run.ainvoke(
        {"ref": "run_" + "0" * 8 + "-0000-0000-0000-000000000000", "pattern": "("}
    )
    assert "matched" in out or "No lines" in out
