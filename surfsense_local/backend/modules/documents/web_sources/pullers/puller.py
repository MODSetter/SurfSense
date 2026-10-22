from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NamedTuple
from urllib.parse import SplitResult

# Items a plugin answered, by tool name.
Results = dict[str, list[dict[str, Any]]]
# Comments and reviews kept in a source, the most relevant first.
MAX_REPLIES = 100


class Fit(StrEnum):
    """How a link on a puller's site fits it."""

    ONE = "one"
    # A channel, profile, playlist, search page, category: opened into its items to pick.
    LIST = "list"
    # A short link the plugin cannot follow; following it would reach another host.
    SHORT_LINK = "short_link"


@dataclass(frozen=True)
class ToolCall:
    tool: str
    arguments: dict[str, Any]
    # The source stands without it, as a video does without its comments.
    optional: bool = False


class Pulled(NamedTuple):
    title: str
    markdown: str


class Listed(NamedTuple):
    """One item of a list, as a row the user may add."""

    url: str
    title: str
    description: str | None


@dataclass(frozen=True)
class Listing:
    # The call that reads a list link's first `count` items.
    call: Callable[[str, int], ToolCall]
    items: Callable[[list[dict[str, Any]]], list[Listed]]


@dataclass(frozen=True)
class Puller:
    # Stored on the note, and shown on a search result.
    id: str
    plugin_id: str
    # None for a link on another site.
    fit: Callable[[SplitResult], Fit | None]
    calls: Callable[[str], list[ToolCall]]
    # None when the plugin found nothing to keep.
    written: Callable[[str, Results], Pulled | None]
    # None for a site with no list links.
    listing: Listing | None = None
