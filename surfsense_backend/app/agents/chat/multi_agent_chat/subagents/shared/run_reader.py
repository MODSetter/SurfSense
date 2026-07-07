"""``read_run`` / ``search_run`` / ``export_run``: work with a stored run or spill.

Scraper capability outputs and evicted context spills are stored full in Postgres
(``runs`` / ``tool_output_spills``); the model only ever sees a capped preview plus
a reference like ``run_<uuid>`` or ``spill_<uuid>``. The read tools retrieve the
rest on demand — line-based paging and pattern search — without ever loading the
whole payload into context. ``export_run`` goes one step further for bulk
datasets: it converts the stored items (or their nested link records) to CSV
**in code** and saves the file as a workspace document, so hundreds of rows never
flow through the model at all. Every lookup is scoped to the caller's workspace
(the trust boundary).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from typing import Annotated, Any
from uuid import UUID

from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy import select

from app.capabilities.core.runs import RUN_OUTPUT_CHAR_CAP
from app.db import Run, ToolOutputSpill, shielded_async_session

logger = logging.getLogger(__name__)

_MAX_LIMIT = 100
_MAX_PATTERN_LEN = 200
"""ReDoS guard: reject/simplify absurdly long model-supplied patterns."""

_EXPORT_MAX_ROWS = 20_000
"""ponytail: hard row cap so a 200-page crawl can't produce a CSV whose
embedding pass stalls the turn. Raise alongside a background-embedding path."""

_ITEM_DEFAULT_FIELDS = ["url", "status", "error"]
_LINK_DEFAULT_FIELDS = ["page", "url", "text", "context", "kind"]


def _parse_ref(ref: str) -> tuple[str, UUID] | None:
    """Split ``run_<uuid>`` / ``spill_<uuid>`` into ``(kind, uuid)``; ``None`` if malformed."""
    ref = (ref or "").strip()
    for prefix, kind in (("run_", "run"), ("spill_", "spill")):
        if ref.startswith(prefix):
            try:
                return kind, UUID(ref[len(prefix) :])
            except ValueError:
                return None
    return None


async def _load_body(ref: str, workspace_id: int) -> tuple[str, str] | str:
    """Return ``(body_text, kind)`` for a ref, or an error string.

    Workspace-scoped: a ref belonging to another workspace reads as not found.
    """
    parsed = _parse_ref(ref)
    if parsed is None:
        return (
            f"Error: '{ref}' is not a valid run reference. "
            "Expected 'run_<uuid>' or 'spill_<uuid>'."
        )
    kind, ref_id = parsed
    async with shielded_async_session() as session:
        if kind == "run":
            row = (
                await session.execute(
                    select(Run.output_text).where(
                        Run.id == ref_id, Run.workspace_id == workspace_id
                    )
                )
            ).scalar_one_or_none()
        else:
            row = (
                await session.execute(
                    select(ToolOutputSpill.content).where(
                        ToolOutputSpill.id == ref_id,
                        ToolOutputSpill.workspace_id == workspace_id,
                    )
                )
            ).scalar_one_or_none()
    if row is None:
        return f"Error: {ref} not found in this workspace."
    return (row or ""), kind


def _cap(body: str) -> str:
    """Clip a response to the shared char cap with an explicit truncation note."""
    if len(body) <= RUN_OUTPUT_CHAR_CAP:
        return body
    return (
        body[:RUN_OUTPUT_CHAR_CAP]
        + f"\n\n...[response truncated at {RUN_OUTPUT_CHAR_CAP} chars; "
        "narrow the pattern or lower max_matches]..."
    )


def _rows_from_body(body: str, rows: str) -> list[dict[str, Any]]:
    """Deterministically flatten stored JSONL into export rows.

    ``rows="items"`` → one row per stored item. ``rows="links"`` → explode each
    item's ``links`` records, prefixing every row with the page it came from.
    Non-JSON lines (plain-text spills) are skipped.
    """
    out: list[dict[str, Any]] = []
    for line in body.split("\n"):
        try:
            item = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(item, dict):
            continue
        if rows == "items":
            out.append(item)
            continue
        page = str(item.get("url") or "")
        for link in item.get("links") or []:
            if isinstance(link, dict):
                out.append({"page": page, **link})
    return out


def _cell(value: Any) -> str:
    """Render one CSV cell: scalars as-is, nested structures as compact JSON."""
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _rows_to_csv(records: list[dict[str, Any]], fields: list[str]) -> tuple[str, int]:
    """Serialize deduplicated rows to CSV text; returns ``(csv_text, row_count)``."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(fields)
    seen: set[tuple[str, ...]] = set()
    count = 0
    for record in records:
        row = tuple(_cell(record.get(field)) for field in fields)
        if row in seen:
            continue
        seen.add(row)
        writer.writerow(row)
        count += 1
        if count >= _EXPORT_MAX_ROWS:
            break
    return buf.getvalue(), count


async def _save_export_document(
    *, virtual_path: str, content: str, workspace_id: int
) -> tuple[int, str] | str:
    """Persist the CSV as a workspace document; ``(doc_id, path)`` or an error string.

    Uses the same canonical create path as end-of-turn KB persistence (folder
    hierarchy + Document + chunks + embeddings), committed immediately — an
    export is deterministic, so there is nothing to stage.
    """
    # Deferred import: kb_persistence lives in the main-agent package, which
    # transitively imports this module — same cycle-avoidance as the tool builder.
    from app.agents.chat.multi_agent_chat.main_agent.middleware.kb_persistence.middleware import (
        _create_document,
    )
    from app.agents.chat.runtime.path_resolver import DOCUMENTS_ROOT
    from app.db import async_session_maker

    path = virtual_path.strip()
    if not path.startswith("/"):
        path = "/" + path
    if not path.startswith(DOCUMENTS_ROOT + "/"):
        path = DOCUMENTS_ROOT + path

    try:
        async with async_session_maker() as session:
            doc = await _create_document(
                session,
                virtual_path=path,
                content=content,
                workspace_id=workspace_id,
                created_by_id=None,
            )
            await session.commit()
            doc_id = doc.id
    except ValueError as exc:
        return f"Error: {exc}. Pick a different path."
    except Exception:
        logger.exception("export_run: document create failed for %s", path)
        return "Error: could not save the export document (storage failure)."

    # Best-effort UI refresh; the document row is already committed.
    try:
        from langchain_core.callbacks import adispatch_custom_event

        await adispatch_custom_event(
            "document_created",
            {"id": doc_id, "title": path.rsplit("/", 1)[-1], "virtualPath": path},
        )
    except Exception:
        logger.debug("export_run: document_created dispatch failed", exc_info=True)
    return doc_id, path


def build_run_reader_tools(*, workspace_id: int) -> list[BaseTool]:
    """Build the ``read_run`` / ``search_run`` / ``export_run`` tools for one workspace."""

    async def _read_run(
        ref: Annotated[
            str, "The run reference to read, e.g. 'run_<uuid>' or 'spill_<uuid>'."
        ],
        offset: Annotated[int, "0-based line (item) index to start from."] = 0,
        limit: Annotated[int, "Max lines (items) to return (default 20)."] = 20,
        char_offset: Annotated[
            int,
            "0-based character index within the selected lines to start from. "
            "Use this to page through a single item bigger than one response "
            "(the truncation note tells you the next char_offset).",
        ] = 0,
    ) -> str:
        loaded = await _load_body(ref, workspace_id)
        if isinstance(loaded, str):
            return loaded
        body, _kind = loaded
        lines = body.split("\n")
        start = max(0, offset)
        count = min(max(1, limit), _MAX_LIMIT)
        window = lines[start : start + count]
        if not window:
            return f"No lines at offset {start} (total {len(lines)} lines in {ref})."
        window_body = "\n".join(window)
        start_char = max(0, char_offset)
        if start_char >= len(window_body) > 0:
            return (
                f"No content at char_offset {start_char} "
                f"(this window is {len(window_body)} chars)."
            )
        remaining = window_body[start_char:]
        shown = remaining[:RUN_OUTPUT_CHAR_CAP]
        header = (
            f"Showing lines {start}-{start + len(window) - 1} of {len(lines)} in {ref}"
            + (f", from char {start_char} of this window" if start_char else "")
            + ":\n"
        )
        if len(remaining) > len(shown):
            left = len(remaining) - len(shown)
            return (
                header
                + shown
                + f"\n\n...[truncated; {left} chars remain in this window — "
                f"continue with char_offset={start_char + len(shown)}, or use "
                "search_run]..."
            )
        return header + shown

    async def _search_run(
        ref: Annotated[str, "The run reference to search, e.g. 'run_<uuid>'."],
        pattern: Annotated[str, "Substring or regular expression to match per line."],
        max_matches: Annotated[int, "Max matching lines to return (default 20)."] = 20,
    ) -> str:
        loaded = await _load_body(ref, workspace_id)
        if isinstance(loaded, str):
            return loaded
        body, _kind = loaded
        pattern = (pattern or "").strip()
        if not pattern:
            return "Error: provide a non-empty search pattern."

        matcher = _build_matcher(pattern)
        limit = min(max(1, max_matches), _MAX_LIMIT)
        matches: list[str] = []
        total = 0
        for idx, line in enumerate(body.split("\n")):
            span = matcher(line)
            if span is not None:
                total += 1
                if len(matches) < limit:
                    matches.append(f"[{idx}] {_excerpt(line, span)}")
        if not matches:
            return f"No lines in {ref} matched {pattern!r}."
        header = (
            f"Found {total} matching line(s) in {ref}"
            f"{f' (showing first {limit})' if total > limit else ''}:\n"
        )
        return _cap(header + "\n".join(matches))

    async def _export_run(
        ref: Annotated[
            str, "The run reference to export, e.g. 'run_<uuid>' or 'spill_<uuid>'."
        ],
        path: Annotated[
            str,
            "Destination file path in the workspace, e.g. "
            "'/documents/exports/a16z-team.csv'.",
        ],
        rows: Annotated[
            str,
            "'links' = one CSV row per link record on each crawled page "
            "(columns like page, url, text, context, kind — use for rosters, "
            "directories, listings). 'items' = one row per stored result item.",
        ] = "links",
        fields: Annotated[
            list[str] | None,
            "Columns to include, in order. Defaults: links -> "
            "page,url,text,context,kind; items -> url,status,error.",
        ] = None,
        include_pattern: Annotated[
            str | None,
            "Only keep rows matching this substring/regex (tested against the "
            "row's combined values), e.g. '/author/' for team-profile links.",
        ] = None,
        exclude_pattern: Annotated[
            str | None, "Drop rows matching this substring/regex."
        ] = None,
    ) -> str:
        loaded = await _load_body(ref, workspace_id)
        if isinstance(loaded, str):
            return loaded
        body, _kind = loaded
        if rows not in ("items", "links"):
            return "Error: rows must be 'items' or 'links'."

        records = _rows_from_body(body, rows)
        if include_pattern:
            inc = _build_matcher(include_pattern.strip())
            records = [
                r for r in records if inc(" ".join(map(_cell, r.values()))) is not None
            ]
        if exclude_pattern:
            exc = _build_matcher(exclude_pattern.strip())
            records = [
                r for r in records if exc(" ".join(map(_cell, r.values()))) is None
            ]
        if not records:
            return (
                f"Error: no rows to export from {ref} "
                f"(rows={rows}, include={include_pattern!r}, exclude={exclude_pattern!r}). "
                "Loosen the filters or check the run with search_run."
            )

        columns = [f for f in (fields or []) if f] or (
            _LINK_DEFAULT_FIELDS if rows == "links" else _ITEM_DEFAULT_FIELDS
        )
        csv_text, row_count = _rows_to_csv(records, columns)

        saved = await _save_export_document(
            virtual_path=path, content=csv_text, workspace_id=workspace_id
        )
        if isinstance(saved, str):
            return saved
        doc_id, final_path = saved

        preview_lines = csv_text.split("\n")[:4]
        truncated_note = (
            f" (capped at {_EXPORT_MAX_ROWS} rows)"
            if row_count >= _EXPORT_MAX_ROWS
            else ""
        )
        return (
            f"Exported {row_count} rows{truncated_note} to {final_path} "
            f"(document id {doc_id}, {len(csv_text)} chars).\n"
            f"Columns: {', '.join(columns)}\n"
            "First lines:\n" + "\n".join(preview_lines)
        )

    return [
        StructuredTool.from_function(
            name="read_run",
            description=(
                "Read a stored scraper run or spilled tool output by line, in pages. "
                "Use the reference from a truncated tool result (e.g. 'run_<uuid>'). "
                "Each line is one result item (JSON). Page with offset/limit; when a "
                "single item is bigger than one response, keep offset fixed and page "
                "inside it with char_offset. Prefer search_run when hunting for "
                "something specific."
            ),
            coroutine=_read_run,
        ),
        StructuredTool.from_function(
            name="search_run",
            description=(
                "Search a stored scraper run or spilled tool output for lines matching "
                "a substring or regular expression. Returns matching items with their "
                "line index. Cheaper than reading the whole run when you know what you "
                "are looking for."
            ),
            coroutine=_search_run,
        ),
        StructuredTool.from_function(
            name="export_run",
            description=(
                "Export a stored run's structured data to a CSV file saved in the "
                "user's workspace — deterministically, in code, without the rows "
                "passing through you. Use for full-dataset requests (a complete "
                "team roster, portfolio list, directory): crawl first, then export "
                "the run instead of re-typing hundreds of rows. rows='links' "
                "explodes each page's link records (filter with include_pattern, "
                "e.g. a profile-URL fragment); rows='items' exports one row per "
                "result item. Identical rows are deduplicated — on multi-page "
                "crawls, omit 'page' from fields so the same link found on many "
                "pages collapses to one row. Returns the saved path, row count, "
                "and a preview."
            ),
            coroutine=_export_run,
        ),
    ]


_EXCERPT_RADIUS = 300
"""Chars shown on each side of a match when the line itself is huge."""


def _excerpt(line: str, match_start: int) -> str:
    """Return the line whole, or a window around the match for oversized lines.

    A crawled page is one JSON line that can run to hundreds of kB; returning it
    verbatim would blow the response cap after one match. The noted char offset
    plugs straight into ``read_run(..., char_offset=)`` for wider context.
    """
    if len(line) <= _EXCERPT_RADIUS * 2:
        return line
    start = max(0, match_start - _EXCERPT_RADIUS)
    end = min(len(line), match_start + _EXCERPT_RADIUS)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(line) else ""
    return (
        f"(match at char {match_start} of {len(line)}) "
        f"{prefix}{line[start:end]}{suffix}"
    )


def _build_matcher(pattern: str):
    """Compile a line matcher returning the match start index, or ``None``.

    Falls back to substring on bad/oversized regex (ReDoS guard).
    """

    def _substring(line: str) -> int | None:
        idx = line.lower().find(pattern.lower())
        return idx if idx >= 0 else None

    if len(pattern) > _MAX_PATTERN_LEN:
        return _substring
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return _substring

    def _regex(line: str) -> int | None:
        m = compiled.search(line)
        return m.start() if m else None

    return _regex
