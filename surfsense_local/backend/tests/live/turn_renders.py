"""What a turn rendered, as versions in Studio, and whether the agent looked at every page of what it ended on."""

import base64
import binascii
import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.agent.previews.inline_images import inline_image
from shared.config import get_storage_settings
from tests.live.live_agent import LiveAgent, steps
from tests.live.recording_proxy import Exchange, image_parts

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


def pages_sent_inline(
    exchanges: Sequence[Exchange], version: Version, previews: Path
) -> set[int]:
    """The pages of a version whose attached image reached the model in a request that came back.

    Matched by the exact JPEG the render attaches, which `read` never sends, so
    neither an opened file nor a refused request stands in for a page.
    """
    sent = {
        hashlib.sha256(data).hexdigest()
        for exchange in exchanges
        if exchange.status == 200 and not exchange.error
        for _, role, url in image_parts(exchange.request)
        if role == "user" and (data := _jpeg_bytes(url)) is not None
    }
    if not sent:
        return set()
    folder = previews / f"{version.id}-v{version.number}"
    return {
        page
        for page in _pages(folder)
        if hashlib.sha256(inline_image(folder / f"page-{page}.png").data).hexdigest()
        in sent
    }


def pages_left_unread(
    frames: list[dict[str, Any]],
    version: Version,
    previews: Path,
    exchanges: Sequence[Exchange] = (),
) -> list[int]:
    """The pages drawn for a version that the agent neither opened nor was sent inline."""
    opened = previews_opened(frames)
    inline = pages_sent_inline(exchanges, version, previews)
    return [
        page
        for page in _pages(previews / f"{version.id}-v{version.number}")
        if (version.id, version.number, page) not in opened and page not in inline
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


def sees_pages(live: LiveAgent) -> bool:
    """Whether the model is sent page previews: the catalog says it reads images."""
    return live.run.model.reads_images


def previews_of(live: LiveAgent, version: Version) -> Path:
    """The previews folder of the thread that drew `version`.

    Each thread draws previews into its own folder; a live run checks one thread.
    """
    threads = get_storage_settings().agent_threads_dir(live.workspace_id)
    return next(
        (
            found
            for found in threads.glob("*/outputs/previews")
            if (found / f"{version.id}-v{version.number}").is_dir()
        ),
        threads / "none" / "outputs" / "previews",
    )


async def assert_pages_checked(
    live: LiveAgent, frames: list[dict[str, Any]], turn: str
) -> None:
    """Every page preview of the version the turn ended on reached the agent: sent inline or opened.

    A text-only model is told to check the script and the render's text instead
    (the skill), so only a model that reads images is held to the previews.
    """
    made = await last_version(live, frames, turn)
    if not sees_pages(live):
        return
    previews = previews_of(live, made)
    assert _pages(previews / f"{made.id}-v{made.number}"), (
        f"{turn}: {made} has no page previews to check"
    )
    unread = pages_left_unread(frames, made, previews, live.proxy.exchanges)
    assert not unread, (
        f"{turn}: page(s) {unread} of {made} were never opened or sent inline"
    )


def _jpeg_bytes(url: str) -> bytes | None:
    head, _, data = url.partition(";base64,")
    if head != "data:image/jpeg" or not data:
        return None
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        return None


def _pages(folder: Path) -> list[int]:
    if not folder.is_dir():
        return []
    return sorted(
        int(match[1])
        for path in folder.iterdir()
        if (match := _PAGE.fullmatch(path.name))
    )
