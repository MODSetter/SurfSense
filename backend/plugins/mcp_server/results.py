"""A tool's result as an agent reads it: the summary, then each item as one line of JSON.

opencode keeps only a result's text when it has any, so an item the text leaves out
is one the agent never sees: its price, its page text, its reviews. Each item goes
in the text, trimmed by the plugin's `project` and capped in bytes, and whole in
`structured_content` for a client that reads it.
"""

import itertools
import json
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import Context
from mcp_types import CallToolResult, TextContent

# Sent by a client that reads only the text, so the items need not go twice.
TEXT_ONLY_HEADER = "x-surfsense-text-only"
# About 8,000 tokens: a page of results, not a context window.
MAX_TEXT_BYTES = 32_000
# A longer string is cut here, so one long field cannot crowd out the other items.
CLIP_CHARS = 2_000
ELLIPSIS = "…"


def tool_result(
    summary: str,
    items: list[dict[str, Any]],
    *,
    project: Callable[[dict[str, Any]], dict[str, Any]],
    max_text_bytes: int = MAX_TEXT_BYTES,
    clip_chars: int = CLIP_CHARS,
    text_only: bool = False,
) -> CallToolResult:
    """The summary, then one compact JSON line per item as `project` picks its fields.

    Nulls, empty strings and empty lists or objects are dropped, and a string longer
    than `clip_chars` ends in an ellipsis. The text stays within `max_text_bytes`:
    the items that do not fit are counted on its last line, and a first item too
    long on its own is cut to fit. `structured_content` holds the items as given,
    unless `text_only`.
    """
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=_text(summary, items, project, max_text_bytes, clip_chars),
            )
        ],
        structured_content=None if text_only else {"items": items},
    )


def wants_text_only(ctx: Context | None) -> bool:
    """Whether the request asked for the text alone, with `x-surfsense-text-only: 1`."""
    try:
        headers = ctx.headers if ctx is not None else None
    except ValueError:
        # Outside a request, as in a test calling the tool directly.
        return False
    value = (headers or {}).get(TEXT_ONLY_HEADER, "")
    return value.strip().lower() in {"1", "true", "yes"}


def more_line(count: int) -> str:
    """The text's last line when `count` items did not fit."""
    # Never "ask for fewer": a smaller max_items returns the same first items again.
    return f"{count} more items not shown: this reply is full"


def _text(
    summary: str,
    items: list[dict[str, Any]],
    project: Callable[[dict[str, Any]], dict[str, Any]],
    max_text_bytes: int,
    clip_chars: int,
) -> str:
    head = summary.rstrip("\n")
    # Made one at a time, so the items past the cap are never serialised: a tool may
    # return thousands, on the loop every plugin shares.
    made = (_made(item, project, clip_chars) for item in items)
    seen: list[tuple[Any, str]] = []
    used = _size(head)
    for value, line in made:
        seen.append((value, line))
        used += _size(line) + (1 if head or len(seen) > 1 else 0)
        if used > max_text_bytes:
            break
    else:
        return "\n".join(part for part in [head, *(line for _, line in seen)] if part)
    # Room is kept for the line counting what is left, should the next item not fit.
    head = _clipped_bytes(head, max_text_bytes - _size(more_line(len(items))) - 1)
    kept = [head]
    used = _size(head)
    for index, (value, line) in enumerate(itertools.chain(seen, made)):
        left = len(items) - index - 1
        room = max_text_bytes - used - 1 - (_size(more_line(left)) + 1 if left else 0)
        fitted: str | None = line
        if _size(line) > room and len(kept) == 1:
            # One item too long for the cap still shows what fits of it.
            fitted = _shrunk(value, room)
        if fitted is None or _size(fitted) > room:
            break
        kept.append(fitted)
        used += _size(fitted) + 1
    shown = len(kept) - 1
    if shown < len(items):
        kept.append(more_line(len(items) - shown))
    return "\n".join(line for line in kept if line)


def _made(
    item: dict[str, Any],
    project: Callable[[dict[str, Any]], dict[str, Any]],
    clip_chars: int,
) -> tuple[Any, str]:
    """The item as `project` picks it, compacted, and its line."""
    value = _compact(project(item), clip_chars)
    return value, _line(value)


def _compact(value: Any, clip_chars: int) -> Any:
    if isinstance(value, dict):
        kept = {key: _compact(inner, clip_chars) for key, inner in value.items()}
        return {key: inner for key, inner in kept.items() if not _empty(inner)}
    if isinstance(value, list | tuple):
        kept_items = [_compact(inner, clip_chars) for inner in value]
        return [inner for inner in kept_items if not _empty(inner)]
    if isinstance(value, str) and len(value) > clip_chars:
        return value[:clip_chars] + ELLIPSIS
    return value


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str | list | dict) and not value)


def _line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _size(text: str) -> int:
    return len(text.encode())


def _clipped_bytes(text: str, limit: int) -> str:
    if _size(text) <= limit:
        return text
    cut = text.encode()[: max(0, limit - _size(ELLIPSIS))]
    return cut.decode(errors="ignore") + ELLIPSIS


def _shrunk(value: Any, room: int) -> str | None:
    """`value`'s line cut to `room` bytes, or None when not even an ellipsis fits.

    A string long enough to take the whole excess, such as a crawled page's text, is
    shortened, so the item's other fields stay whole. Otherwise the size is in many
    strings or a long list, a place's reviews or a transcript's segments, and the
    line itself is cut, so the agent still reads the item's start.
    """
    for _ in range(8):
        line = _line(value)
        over = _size(line) - room
        if over <= 0:
            return line
        longest = _longest(value)
        # A character is at least one byte in the line, so cutting `over` of them fits;
        # a few more make room for the ellipsis.
        keep = longest - over - 4
        if keep < 1:
            break
        value = _cut_longest(value, longest, keep)
    return _clipped_bytes(_line(value), room) if room > _size(ELLIPSIS) else None


def _longest(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return max((_longest(inner) for inner in value.values()), default=0)
    if isinstance(value, list):
        return max((_longest(inner) for inner in value), default=0)
    return 0


def _cut_longest(value: Any, longest: int, keep: int) -> Any:
    """`value` with its first string of `longest` characters cut to `keep`."""
    done = False

    def cut(inner: Any) -> Any:
        nonlocal done
        if done:
            return inner
        if isinstance(inner, str) and len(inner) == longest:
            done = True
            return inner[:keep].removesuffix(ELLIPSIS) + ELLIPSIS
        if isinstance(inner, dict):
            return {key: cut(item) for key, item in inner.items()}
        if isinstance(inner, list):
            return [cut(item) for item in inner]
        return inner

    return cut(value)
