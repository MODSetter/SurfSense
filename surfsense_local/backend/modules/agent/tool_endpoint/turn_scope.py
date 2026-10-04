"""Which sources one agent turn may use, as SurfSense's tools learn it.

A tool call names no turn, so each turn registers the tools at an address
carrying a token, and the token maps to the turn's ticked sources here, in this
process only: a restart forgets them, and a call with a token it never issued
is refused rather than given the whole workspace.
"""

import secrets
import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from modules.agent.tool_endpoint.tool import ToolCallError

# The query parameter the token rides in.
PARAMETER = "scope"
# Longer than any turn runs; a turn still running past it is refused, not widened.
KEEP_SECONDS = 24 * 60 * 60

_UNKNOWN = (
    "SurfSense cannot tell which sources this request may use, so this tool "
    "cannot run. Ask the user to send the message again."
)


@dataclass(frozen=True)
class TurnScope:
    """The workspace a tool call is for, and the sources its turn may use."""

    workspace_id: int
    # The ticked sources; None is the whole workspace, as a chat message without `document_ids`.
    document_ids: frozenset[int] | None
    # False when the call carried no token this process issued for the workspace.
    known: bool = True

    def selected(self) -> frozenset[int] | None:
        """The ticked sources, None for the whole workspace; refused when the turn is unknown."""
        if not self.known:
            raise ToolCallError(_UNKNOWN)
        return self.document_ids

    def refuse_unselected(self, source_ids: Iterable[int]) -> None:
        """Refuse a call naming a source the turn may not use, saying what it may."""
        selected = self.selected()
        if selected is None:
            return
        outside = [i for i in dict.fromkeys(source_ids) if i not in selected]
        if not outside:
            return
        named = ", ".join(map(str, outside))
        refused = (
            f"Source {named} is not selected for this request."
            if len(outside) == 1
            else f"Sources {named} are not selected for this request."
        )
        raise ToolCallError(f"{refused} {_what_is_selected(selected)}")


def _what_is_selected(selected: frozenset[int]) -> str:
    if not selected:
        return "The user selected no sources: ask them to select the ones to use."
    ids = ", ".join(map(str, sorted(selected)))
    return (
        f"The user selected: {ids}. Use only those, or ask the user to select "
        "more sources."
    )


_lock = threading.Lock()
_scopes: dict[str, tuple[TurnScope, float]] = {}


def remember_turn_scope(workspace_id: int, document_ids: Sequence[int] | None) -> str:
    """A new token for a turn's scope; scopes older than KEEP_SECONDS are dropped."""
    token = secrets.token_urlsafe(16)
    ids = None if document_ids is None else frozenset(document_ids)
    now = time.monotonic()
    with _lock:
        for old in [t for t, (_, made) in _scopes.items() if now - made > KEEP_SECONDS]:
            del _scopes[old]
        _scopes[token] = (TurnScope(workspace_id, ids), now)
    return token


def turn_scope(token: str | None, workspace_id: int) -> TurnScope:
    """The scope a token was issued for, or an unknown one that tools reading sources refuse."""
    with _lock:
        found = _scopes.get(token) if token else None
    if (
        found is None
        or found[0].workspace_id != workspace_id
        or time.monotonic() - found[1] > KEEP_SECONDS
    ):
        return TurnScope(workspace_id, None, known=False)
    return found[0]
