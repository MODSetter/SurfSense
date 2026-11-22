"""A thread's stored ticks, and beside them the sources its messages named with `@`.

Both live in `chat_threads.source_scope`, so a mention needs no migration. A send
replaces the ticks, never these: a follow-up can still read what an earlier message named.
"""

from collections.abc import Sequence
from typing import Any

from modules.source_scope.schemas import SourceScope

_KEY = "mentioned_document_ids"


def ticks_of(stored: dict[str, Any]) -> dict[str, Any]:
    """The stored JSON as `SourceScope` reads it, which refuses any other key."""
    return {key: value for key, value in stored.items() if key != _KEY}


def mentioned_of(stored: dict[str, Any] | None) -> list[int]:
    return list((stored or {}).get(_KEY, []))


def stored_with_mentions(
    scope: SourceScope, mentioned: Sequence[int]
) -> dict[str, Any]:
    stored = scope.model_dump()
    # Left out when empty, so a thread that names nothing stores what it always did.
    return {**stored, _KEY: list(mentioned)} if mentioned else stored


def with_mentions(scope: SourceScope, mentioned: Sequence[int]) -> SourceScope:
    """The scope a turn works from: naming a source overrides unticking it.

    `document_ids` beat a folder's exclusion but not `excluded_document_ids`. Copied
    without validation, as MAX_SCOPE_IDS bounds a request and a named folder can hold more.
    """
    if not mentioned:
        return scope
    named = set(mentioned)
    return scope.model_copy(
        update={
            "document_ids": list(dict.fromkeys([*scope.document_ids, *mentioned])),
            "excluded_document_ids": [
                i for i in scope.excluded_document_ids if i not in named
            ],
        }
    )
