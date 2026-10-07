"""A ready version's page previews as a tool result carries them: images, then what to do with them."""

import logging
import re
import time
from pathlib import Path

from modules.agent.opencode_config import CONFIG_FILE, declares_image_input
from modules.agent.previews import previews_for
from modules.agent.previews.inline_images import inline_image
from modules.agent.tool_endpoint.tool import InlineImage
from modules.artifacts.models import Artifact
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

# The snapshot page lays Word out with docx-preview, told to skip both
# (frontend/src/features/docx-snapshot/snapshot-page.ts).
WORD_PREVIEWS_LEAVE_OUT = (
    "Drawn by SurfSense's Word viewer. Word previews leave out headers and "
    "footers: a logo or page number placed there is in the document even though "
    "no preview shows it."
)
# The snapshot page lays a deck out with pptx-renderer, the Studio viewer's library.
SLIDE_PREVIEWS_DIFFER = (
    "Slide previews show the deck as SurfSense's slide viewer draws it, which can "
    "differ a little from PowerPoint in fonts and charts."
)
LOOK_AT_EVERY_PAGE = (
    "Look at every one before you answer; if one is wrong, fix the script, render "
    "again and look at the new version's pages too."
)
_PAGE_FILE = re.compile(r"page-(\d+)\.png")


def drawn_by_office(office: str) -> str:
    """Which renderer drew the pages, when LibreOffice did; a QA signal, not Word's own layout."""
    return (
        f"Drawn by {office}, which lays the file out much as Word and PowerPoint "
        "do, headers and footers included; fonts can still differ a little."
    )


def version_pages(
    artifact: Artifact,
    version: int,
    folder: Path,
    deadline: float,
    look: str = LOOK_AT_EVERY_PAGE,
) -> tuple[str, tuple[InlineImage, ...]]:
    """The preview pages as images, what to do with them (`look`), and why any are missing.

    The paths are not listed one by one, so the model is not invited to open
    each page again with `read`, which would send every page twice.
    """
    if not declares_image_input(get_storage_settings().agent_dir / CONFIG_FILE):
        return (
            "No page previews: the selected model cannot read images. Check the "
            "script and the text above instead."
        ), ()
    try:
        previews = previews_for(artifact, folder, time_left=deadline - time.monotonic())
    # The version is made; a preview that breaks must not send the model to make it again.
    except Exception:
        logger.exception("previews of artifact %s failed", artifact.id)
        return "No page previews: drawing them failed.", ()
    if not previews.pages:
        return f"No page previews: {previews.reason or 'none were drawn.'}", ()
    kept_in = _relative(previews.pages[0].parent, folder)
    shown: list[int] = []
    images: list[InlineImage] = []
    unattached: list[str] = []
    for number, page in sorted((_page_number(p), p) for p in previews.pages):
        try:
            images.append(inline_image(page))
        # A page that will not encode costs that page, never the made version.
        except Exception:
            logger.exception("page %s of artifact %s not attached", number, artifact.id)
            unattached.append(
                f"Page {number} could not be attached; open "
                f"{_relative(page, folder)} with read."
            )
            continue
        shown.append(number)
    if not images:
        return (
            "No page previews: they were drawn but could not be attached; open "
            f"them in {kept_in}/ with read."
        ), ()
    unit = "slide" if artifact.format == "pptx" else "page"
    if previews.drawn_by_office is not None:
        caveat = [drawn_by_office(previews.drawn_by_office)]
    else:
        caveat = {
            "docx": [WORD_PREVIEWS_LEAVE_OUT],
            "pptx": [SLIDE_PREVIEWS_DIFFER],
        }.get(artifact.format, [])
    text = "\n".join(
        [
            f"The {unit} previews of version {version} of artifact "
            f"{artifact.id} come with this result as images, in order: "
            f"{', '.join(f'{unit} {n}' for n in shown)}.",
            look,
            *([previews.reason] if previews.reason else []),
            *unattached,
            *caveat,
            f"Larger copies are in {kept_in}/ as page-<n>.png; open one with read "
            "only for a closer look.",
        ]
    )
    return text, tuple(images)


def _page_number(page: Path) -> int:
    """The number in the file's name: a page too thin to draw leaves a gap."""
    match = _PAGE_FILE.fullmatch(page.name)
    if match is None:
        raise ValueError(f"not a page preview: {page.name}")
    return int(match[1])


def _relative(page: Path, folder: Path) -> str:
    """As the agent names files: from its own folder, with forward slashes."""
    return page.relative_to(folder).as_posix()
