"""The note telling the agent which sources the user named with `@` in this message.

A mirrored path rather than a title: a title is the user's or a file's own text, and
a small model guesses a file's name rather than looking for it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from modules.agent.agent_threads.scope_note import UNSAID
from modules.agent.thread_folder.layout import SOURCES


@dataclass(frozen=True)
class NamedFile:
    path: PurePosixPath
    # A Studio or agent document: what `surfsense_read_document` takes.
    artifact_id: int | None = None


def mention_note(files: Sequence[NamedFile], more: int, unreadable: int) -> str | None:
    """`more` are named but past the listed; `unreadable` have no text to read."""
    if not files and not more and not unreadable:
        return None
    lines = ["The user named these sources in their message. Start from them."]
    lines += [
        f'- "{SOURCES}/{file.path}"'
        + (f" (artifact {file.artifact_id})" if file.artifact_id is not None else "")
        for file in files
    ]
    if more:
        lines.append(f"- and {more} more in {SOURCES}/")
    if unreadable:
        lines.append(
            f"{unreadable} more they named cannot be read as text; say so if the "
            "request needs it."
        )
    lines.append(UNSAID)
    return "\n".join(lines)
