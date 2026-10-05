"""Which sources a tool call may use: its thread's stored scope, as it resolves now.

A tool call names no turn, so each thread registers the tools at its own
address in its own opencode instance; the address names the thread, and the
thread's scope is read on each call, so ticks stored between turns hold.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import SOURCES
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.chat.models import ChatThread
from modules.source_scope.resolve import resolve_scope
from modules.source_scope.thread_scope import thread_scope
from shared.config import get_storage_settings

# Past this many, a refusal points at sources/ instead: 5,000 ids are about 30 KB.
NAMED_IDS = 20

_UNKNOWN = (
    "SurfSense cannot tell which sources this request may use, so this tool "
    "cannot run. Ask the user to send the message again."
)


@dataclass(frozen=True)
class TurnScope:
    """The workspace and thread a tool call is for, its folder, and the sources it may use."""

    workspace_id: int
    thread_id: int
    folder: Path
    document_ids: frozenset[int]
    # False when the address names no agent thread of the workspace.
    known: bool = True

    def require_known(self) -> None:
        """Refuse a call from an address naming no agent thread of the workspace."""
        if not self.known:
            raise ToolCallError(_UNKNOWN)

    def selected(self) -> frozenset[int]:
        """The sources the thread may use; refused when the thread is unknown."""
        self.require_known()
        return self.document_ids

    def refuse_unselected(self, source_ids: Iterable[int]) -> None:
        """Refuse a call naming a source the thread may not use, saying what it may."""
        selected = self.selected()
        outside = [i for i in dict.fromkeys(source_ids) if i not in selected]
        if not outside:
            return
        named = ", ".join(map(str, outside[:NAMED_IDS]))
        if len(outside) > NAMED_IDS:
            named += f" and {len(outside) - NAMED_IDS} more"
        refused = (
            f"Source {named} is not selected for this request."
            if len(outside) == 1
            else f"Sources {named} are not selected for this request."
        )
        raise ToolCallError(f"{refused} {_what_is_selected(selected)}")


def thread_turn_scope(session: Session, workspace_id: int, thread_id: int) -> TurnScope:
    """The thread's scope now; unknown unless it is an agent thread of the workspace."""
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    thread = session.get(ChatThread, thread_id)
    if thread is None or thread.workspace_id != workspace_id or not thread.uses_agent:
        return TurnScope(workspace_id, thread_id, folder, frozenset(), known=False)
    resolved = resolve_scope(session, workspace_id, thread_scope(thread))
    return TurnScope(workspace_id, thread_id, folder, frozenset(resolved.ids))


def _what_is_selected(selected: frozenset[int]) -> str:
    if not selected:
        return "The user selected no sources: ask them to select the ones to use."
    ids = sorted(selected)
    named = ", ".join(map(str, ids[:NAMED_IDS]))
    if len(ids) > NAMED_IDS:
        named += f" and {len(ids) - NAMED_IDS} more: the files in {SOURCES}/"
    return (
        f"The user selected: {named}. Use only those, or ask the user to select "
        "more sources."
    )
