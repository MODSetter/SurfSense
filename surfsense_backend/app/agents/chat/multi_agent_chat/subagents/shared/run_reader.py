"""``read_run`` / ``search_run``: page and grep a stored run or spill by line.

Scraper capability outputs and evicted context spills are stored full in Postgres
(``runs`` / ``tool_output_spills``); the model only ever sees a capped preview plus
a reference like ``run_<uuid>`` or ``spill_<uuid>``. These two tools let the agent
retrieve the rest on demand — line-based paging and pattern search — without ever
loading the whole payload into context. Every lookup is scoped to the caller's
workspace (the trust boundary).
"""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy import select

from app.capabilities.core.runs import RUN_OUTPUT_CHAR_CAP
from app.db import Run, ToolOutputSpill, shielded_async_session

_MAX_LIMIT = 100
_MAX_PATTERN_LEN = 200
"""ReDoS guard: reject/simplify absurdly long model-supplied patterns."""


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
        "narrow with a larger offset or use search_run]..."
    )


def build_run_reader_tools(*, workspace_id: int) -> list[BaseTool]:
    """Build the ``read_run`` / ``search_run`` tools bound to one workspace."""

    async def _read_run(
        ref: Annotated[
            str, "The run reference to read, e.g. 'run_<uuid>' or 'spill_<uuid>'."
        ],
        offset: Annotated[int, "0-based line (item) index to start from."] = 0,
        limit: Annotated[int, "Max lines (items) to return (default 20)."] = 20,
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
            return (
                f"No lines at offset {start} (total {len(lines)} lines in {ref})."
            )
        header = (
            f"Showing lines {start}-{start + len(window) - 1} of {len(lines)} in {ref}:\n"
        )
        return _cap(header + "\n".join(window))

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
            if matcher(line):
                total += 1
                if len(matches) < limit:
                    matches.append(f"[{idx}] {line}")
        if not matches:
            return f"No lines in {ref} matched {pattern!r}."
        header = (
            f"Found {total} matching line(s) in {ref}"
            f"{f' (showing first {limit})' if total > limit else ''}:\n"
        )
        return _cap(header + "\n".join(matches))

    return [
        StructuredTool.from_function(
            name="read_run",
            description=(
                "Read a stored scraper run or spilled tool output by line, in pages. "
                "Use the reference from a truncated tool result (e.g. 'run_<uuid>'). "
                "Each line is one result item (JSON). Page with offset/limit; prefer "
                "search_run when hunting for something specific."
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
    ]


def _build_matcher(pattern: str):
    """Compile a line matcher; fall back to substring on bad/oversized regex (ReDoS guard)."""
    if len(pattern) > _MAX_PATTERN_LEN:
        return lambda line: pattern in line
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return lambda line: pattern.lower() in line.lower()
    return lambda line: compiled.search(line) is not None
