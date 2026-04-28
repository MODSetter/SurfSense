"""Reducers and sentinels for SurfSense filesystem state.

These reducers back the extra state fields used by the cloud-mode filesystem
agent (`cwd`, `staged_dirs`, `pending_moves`, `dirty_paths`, `doc_id_by_path`,
`kb_priority`, `kb_matched_chunk_ids`, `kb_anon_doc`, `tree_version`).

Tools mutate these fields ONLY via `Command(update={...})` returns; the
reducers are responsible for merging successive updates atomically and for
honouring an explicit reset sentinel (`_CLEAR`) so that a single update can
both reset and reseed a list (used by `move_file` / `aafter_agent`).

The sentinel is intentionally a plain string constant rather than a custom
object so that LangGraph's checkpointer (which serializes raw `Command.update`
deltas via ``ormsgpack`` BEFORE reducers are applied) can round-trip writes
that contain it. The token uses a NUL-bracketed form that cannot collide with
any real virtual path, document title, or dict key produced by the agent.
"""

from __future__ import annotations

from typing import Any, Final, TypeVar

_CLEAR: Final[str] = "\x00__SURFSENSE_FILESYSTEM_CLEAR__\x00"
"""Reset sentinel; pass it inside a list/dict update to request a reset.

For list reducers: ``[_CLEAR, *items]`` resets the field then appends ``items``.
For dict reducers: ``{_CLEAR: True, **items}`` resets the field then merges ``items``.

Because the value is a plain string with embedded NUL bytes, it is natively
serializable by ``ormsgpack`` (used by LangGraph's PostgreSQL checkpointer)
yet still distinct from any real path / key produced by application code.
"""


T = TypeVar("T")


def _replace_reducer[T](left: T | None, right: T | None) -> T | None:
    """Replace `left` outright with `right`. ``None`` on the right is honored as a reset."""
    return right


def _is_clear(value: Any) -> bool:
    return isinstance(value, str) and value == _CLEAR


def _add_unique_reducer(
    left: list[Any] | None,
    right: list[Any] | None,
) -> list[Any]:
    """Append items from ``right`` to ``left`` while preserving uniqueness.

    Semantics:
    - If ``right`` is ``None`` or empty, return ``left`` unchanged.
    - If ``right`` contains the ``_CLEAR`` sentinel anywhere, the result is
      reseeded with only the items that appear AFTER the LAST occurrence of
      ``_CLEAR`` (deduplicated, preserving first-seen order). This gives a
      single-update "reset and reseed" capability.
    - Otherwise, items from ``right`` are appended to ``left`` (order preserved
      from first seen) while skipping values that are already present.
    """
    if right is None:
        return list(left or [])
    if not right:
        return list(left or [])

    last_clear = -1
    for index, item in enumerate(right):
        if _is_clear(item):
            last_clear = index

    if last_clear >= 0:
        seed: list[Any] = []
        seen: set[Any] = set()
        for item in right[last_clear + 1 :]:
            if _is_clear(item):
                continue
            try:
                if item in seen:
                    continue
                seen.add(item)
            except TypeError:
                if item in seed:
                    continue
            seed.append(item)
        return seed

    base = list(left or [])
    try:
        seen: set[Any] = set(base)
    except TypeError:
        seen = set()
    for item in right:
        if _is_clear(item):
            continue
        try:
            if item in seen:
                continue
            seen.add(item)
        except TypeError:
            if item in base:
                continue
        base.append(item)
    return base


def _list_append_reducer(
    left: list[Any] | None,
    right: list[Any] | None,
) -> list[Any]:
    """Append items from ``right`` to ``left`` preserving order and duplicates.

    Honours the ``_CLEAR`` sentinel exactly like :func:`_add_unique_reducer`,
    but does NOT deduplicate. Used for queues whose ordering and duplicate
    occurrences matter (e.g. ``pending_moves``).
    """
    if right is None:
        return list(left or [])
    if not right:
        return list(left or [])

    last_clear = -1
    for index, item in enumerate(right):
        if _is_clear(item):
            last_clear = index

    if last_clear >= 0:
        return [item for item in right[last_clear + 1 :] if not _is_clear(item)]

    base = list(left or [])
    base.extend(item for item in right if not _is_clear(item))
    return base


def _dict_merge_with_tombstones_reducer(
    left: dict[Any, Any] | None,
    right: dict[Any, Any] | None,
) -> dict[Any, Any]:
    """Merge ``right`` into ``left`` with two extra capabilities:

    * Keys whose value is ``None`` are removed from the merged result
      (tombstone semantics, matching the deepagents file-data reducer).
    * The special key ``_CLEAR`` (with any truthy value) resets ``left`` to
      ``{}`` before merging the remaining keys from ``right``. This makes it
      possible to atomically clear and reseed the dictionary in a single
      update.
    """
    if right is None:
        return dict(left or {})

    if _CLEAR in right or any(_is_clear(k) for k in right):
        result: dict[Any, Any] = {}
        for key, value in right.items():
            if _is_clear(key):
                continue
            if value is None:
                result.pop(key, None)
                continue
            result[key] = value
        return result

    if left is None:
        return {key: value for key, value in right.items() if value is not None}

    result = dict(left)
    for key, value in right.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = value
    return result


def _initial_filesystem_state() -> dict[str, Any]:
    """Default empty values for SurfSense filesystem state fields.

    Consumers should always treat these fields as ``state.get(key) or
    DEFAULT`` so that fresh threads (without checkpointed state) work
    correctly.
    """
    return {
        "cwd": "/documents",
        "staged_dirs": [],
        "pending_moves": [],
        "doc_id_by_path": {},
        "dirty_paths": [],
        "kb_priority": [],
        "kb_matched_chunk_ids": {},
        "kb_anon_doc": None,
        "tree_version": 0,
    }


__all__ = [
    "_CLEAR",
    "_add_unique_reducer",
    "_dict_merge_with_tombstones_reducer",
    "_initial_filesystem_state",
    "_list_append_reducer",
    "_replace_reducer",
]
