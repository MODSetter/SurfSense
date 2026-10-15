"""One page of a document's script, small enough that opencode hands it to the model whole.

opencode cuts a tool result past 2,000 lines or 50 KB and keeps the rest in a
folder every workspace's agent can read, so a long script is read in pages.
"""

from dataclasses import dataclass

# Below opencode's cut, with room for the lines around the page.
PAGE_LINES = 1000
PAGE_BYTES = 40_000


@dataclass(frozen=True)
class ScriptPage:
    text: str  # the lines exactly as the script has them, line ends included
    first: int  # 1-based, as the offset names lines
    last: int
    total: int


class OffsetOutOfRangeError(ValueError):
    """The offset names a line the script does not have."""


def page_of(script: str, offset: int) -> ScriptPage:
    """The lines from `offset` on, up to a page's lines and bytes; never fewer than one."""
    lines = _lines(script)
    if not 1 <= offset <= len(lines):
        raise OffsetOutOfRangeError(offset)
    taken: list[str] = []
    size = 0
    for line in lines[offset - 1 :]:
        size += len(line.encode())
        if taken and (len(taken) == PAGE_LINES or size > PAGE_BYTES):
            break
        taken.append(line)
    return ScriptPage(
        text="".join(taken),
        first=offset,
        last=offset + len(taken) - 1,
        total=len(lines),
    )


def _lines(script: str) -> list[str]:
    """Split at newlines only, as opencode counts them, each line keeping its end."""
    *ended, rest = script.split("\n")
    return [f"{line}\n" for line in ended] + ([rest] if rest else [])
