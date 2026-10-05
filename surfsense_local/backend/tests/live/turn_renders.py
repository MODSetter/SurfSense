"""What a turn rendered, as versions in Studio, and whether the agent looked at every page of what it ended on."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.config import get_storage_settings
from tests.live.live_agent import LiveAgent, steps

_PREVIEW = re.compile(r"previews[/\\](\d+)-v(\d+)[/\\]page-(\d+)\.png")
_PAGE = re.compile(r"page-(\d+)\.png")
RENDER = "surfsense_render_document"


@dataclass(frozen=True)
class Version:
    id: int
    format: str
    root: int
    number: int


def rendered_ids(frames: list[dict[str, Any]]) -> list[int]:
    """The artifact of each render that made a version, in the order they ran."""
    return [
        s["artifact"]["id"]
        for s in steps(frames, RENDER)
        if s["status"] == "completed" and s.get("artifact")
    ]


def ready_versions(artifacts: list[dict[str, Any]]) -> dict[tuple[str, int], list[int]]:
    """Each document's ready version numbers, oldest first, keyed by (format, root).

    A render whose script failed still takes its version number, so a document
    can start at v2: its first ready version is not always v1.
    """
    documents: dict[tuple[str, int], list[int]] = {}
    for artifact in artifacts:
        version = artifact["version"]
        if artifact["status"] != "ready" or version is None:
            continue
        key = (artifact["format"], version["root_id"])
        documents.setdefault(key, []).append(version["number"])
    return {key: sorted(numbers) for key, numbers in sorted(documents.items())}


def previews_opened(frames: list[dict[str, Any]]) -> set[tuple[int, int, int]]:
    """(artifact id, version, page) of every page preview the agent opened with read."""
    opened = set()
    for step in steps(frames, "read"):
        if step["status"] != "completed":
            continue
        match = _PREVIEW.search(str((step.get("input") or {}).get("filePath", "")))
        if match:
            opened.add((int(match[1]), int(match[2]), int(match[3])))
    return opened


def pages_left_unread(
    frames: list[dict[str, Any]], version: Version, previews: Path
) -> list[int]:
    """The pages drawn for a version that the agent never opened."""
    opened = previews_opened(frames)
    return [
        page
        for page in _pages(previews / f"{version.id}-v{version.number}")
        if (version.id, version.number, page) not in opened
    ]


async def last_version(
    live: LiveAgent, frames: list[dict[str, Any]], turn: str
) -> Version:
    """The newest version a turn rendered; the turn must have rendered one."""
    ready = {
        a["id"]: a
        for a in await live.artifacts()
        if a["status"] == "ready" and a["version"] is not None
    }
    made = [
        Version(
            id_,
            ready[id_]["format"],
            ready[id_]["version"]["root_id"],
            ready[id_]["version"]["number"],
        )
        for id_ in rendered_ids(frames)
        if id_ in ready
    ]
    assert made, f"{turn}: no version was rendered"
    return made[-1]


def assert_next_version(earlier: Version, later: Version, turn: str) -> None:
    """An edit is a later version of the same document, in the same format."""
    assert (later.root, later.format) == (earlier.root, earlier.format), (
        f"{turn}: made {later}, not a version of {earlier}"
    )
    assert later.number > earlier.number, f"{turn}: {later} is not newer than {earlier}"


async def assert_pages_checked(
    live: LiveAgent, frames: list[dict[str, Any]], turn: str
) -> None:
    """The agent opened every page preview of the version it ended the turn on."""
    made = await last_version(live, frames, turn)
    previews = (
        get_storage_settings().agent_working_dir(live.workspace_id)
        / "outputs"
        / "previews"
    )
    assert _pages(previews / f"{made.id}-v{made.number}"), (
        f"{turn}: {made} has no page previews to check"
    )
    unread = pages_left_unread(frames, made, previews)
    assert not unread, f"{turn}: the agent never opened page(s) {unread} of {made}"


def _pages(folder: Path) -> list[int]:
    if not folder.is_dir():
        return []
    return sorted(
        int(match[1])
        for path in folder.iterdir()
        if (match := _PAGE.fullmatch(path.name))
    )
