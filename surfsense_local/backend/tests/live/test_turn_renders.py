"""What a turn rendered and which page previews reached the agent, read from its frames and requests."""

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from modules.agent.previews.inline_images import inline_image
from tests.live.recording_proxy import Exchange
from tests.live.turn_renders import (
    Version,
    assert_pages_checked,
    pages_left_unread,
    pages_sent_inline,
    previews_opened,
    ready_versions,
    rendered_ids,
)

pytestmark = pytest.mark.unit


def _step(id_: str, tool: str, status: str, **extra) -> dict:
    return {"type": "agent-step", "id": id_, "tool": tool, "status": status, **extra}


def test_only_renders_that_completed_with_a_version_count() -> None:
    """A failed or unfinished render made no version to check."""
    frames = [
        _step("a", "surfsense_render_document", "running"),
        _step("a", "surfsense_render_document", "completed", artifact={"id": 4}),
        _step("b", "surfsense_render_document", "error", artifact=None),
        _step("c", "surfsense_render_document", "completed", artifact={"id": 6}),
        _step("d", "read", "completed", input={"filePath": "x"}),
    ]

    assert rendered_ids(frames) == [4, 6]


def test_previews_opened_are_named_by_artifact_version_and_page() -> None:
    """opencode gives a relative or an absolute path; a failed read saw nothing."""
    frames = [
        _step(
            "a",
            "read",
            "completed",
            input={"filePath": "outputs/previews/4-v2/page-1.png"},
        ),
        _step(
            "b",
            "read",
            "completed",
            input={"filePath": r"C:\work\agent\outputs\previews\6-v1\page-2.png"},
        ),
        _step(
            "c", "read", "error", input={"filePath": "outputs/previews/7-v1/page-1.png"}
        ),
        _step("d", "read", "completed", input={"filePath": "sources/figures/1-1.png"}),
    ]

    assert previews_opened(frames) == {(4, 2, 1), (6, 1, 2)}


def test_a_page_the_version_has_but_the_agent_never_opened_is_left_unread(
    tmp_path: Path,
) -> None:
    """A near-empty second page is only caught by opening every page."""
    pages = tmp_path / "5-v3"
    pages.mkdir()
    for n in (1, 2):
        (pages / f"page-{n}.png").write_bytes(b"png")
    frames = [
        _step(
            "a",
            "read",
            "completed",
            input={"filePath": "outputs/previews/5-v3/page-1.png"},
        ),
        _step(
            "b",
            "read",
            "completed",
            input={"filePath": "outputs/previews/5-v2/page-2.png"},
        ),
    ]

    unread = pages_left_unread(frames, Version(5, "docx", 1, 3), tmp_path)

    assert unread == [2]


def test_a_document_whose_first_render_failed_starts_at_v2() -> None:
    """A failed render keeps its number, so a PDF made on the second try is v2 and v3."""
    artifacts = [
        {"status": "ready", "format": "docx", "version": {"root_id": 1, "number": 2}},
        {"status": "ready", "format": "docx", "version": {"root_id": 1, "number": 1}},
        {"status": "failed", "format": "pdf", "version": {"root_id": 4, "number": 1}},
        {"status": "ready", "format": "pdf", "version": {"root_id": 4, "number": 3}},
        {"status": "ready", "format": "pdf", "version": {"root_id": 4, "number": 2}},
        {"status": "generating", "format": "pdf", "version": None},
    ]

    assert ready_versions(artifacts) == {("docx", 1): [1, 2], ("pdf", 4): [2, 3]}


def _live(reads_images: bool) -> SimpleNamespace:
    """A run whose one render made v1 of a Word file, with no page previews drawn."""

    async def artifacts() -> list[dict]:
        return [
            {
                "id": 9,
                "status": "ready",
                "format": "docx",
                "version": {"root_id": 9, "number": 1},
            }
        ]

    return SimpleNamespace(
        workspace_id=987654321,
        artifacts=artifacts,
        run=SimpleNamespace(model=SimpleNamespace(reads_images=reads_images)),
        proxy=SimpleNamespace(exchanges=[]),
    )


_RENDERED = [_step("a", "surfsense_render_document", "completed", artifact={"id": 9})]


async def test_a_model_that_reads_images_is_held_to_the_page_previews() -> None:
    """With nothing opened, a model sent previews has not checked its pages."""
    with pytest.raises(AssertionError, match="no page previews to check"):
        await assert_pages_checked(_live(reads_images=True), _RENDERED, "turn 1")


async def test_a_text_only_model_checks_the_script_not_the_previews() -> None:
    """The skill tells a model read cannot show images to skip them, so its render is enough."""
    await assert_pages_checked(_live(reads_images=False), _RENDERED, "turn 1")


async def test_a_text_only_model_still_has_to_render_a_version() -> None:
    """Skipping the previews does not excuse a turn that rendered nothing."""
    with pytest.raises(AssertionError, match="no version was rendered"):
        await assert_pages_checked(_live(reads_images=False), [], "turn 1")


def _drawn(tmp_path: Path, pages: int) -> Path:
    """Real page previews of v1 of artifact 5, each a different colour."""
    folder = tmp_path / "5-v1"
    folder.mkdir()
    for n in range(1, pages + 1):
        colour = (40 * n, 120, 200 - 40 * n)
        Image.new("RGB", (1000, 1415), colour).save(folder / f"page-{n}.png")
    return folder


def _carrying(url: str, status: int = 200, role: str = "user") -> Exchange:
    """A request whose message after the tool step holds one image."""
    message = {
        "role": role,
        "content": [
            {"type": "text", "text": "Attached media from tool result:"},
            {"type": "image_url", "image_url": {"url": url}},
        ],
    }
    return Exchange(request={"messages": [message]}, status=status)


def _url(mime: str, data: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


_V1 = Version(5, "pdf", 5, 1)


def test_a_page_whose_inline_image_reached_the_model_was_sent(tmp_path: Path) -> None:
    """The exact bytes the render attached, in a request that came back."""
    folder = _drawn(tmp_path, 2)
    page_1 = inline_image(folder / "page-1.png").data
    sent = [_carrying(_url("image/jpeg", page_1))]

    assert pages_sent_inline(sent, _V1, tmp_path) == {1}
    assert pages_left_unread([], _V1, tmp_path, sent) == [2]


def test_a_page_opened_with_read_is_not_sent_inline(tmp_path: Path) -> None:
    """`read` sends the PNG on disk, never the attached JPEG."""
    folder = _drawn(tmp_path, 1)
    png = (folder / "page-1.png").read_bytes()

    sent = [_carrying(_url("image/png", png))]

    assert pages_sent_inline(sent, _V1, tmp_path) == set()


def test_a_request_the_provider_refused_sent_nothing(tmp_path: Path) -> None:
    """A 400 means the model never saw the image."""
    folder = _drawn(tmp_path, 1)
    page_1 = inline_image(folder / "page-1.png").data

    sent = [_carrying(_url("image/jpeg", page_1), status=400)]

    assert pages_sent_inline(sent, _V1, tmp_path) == set()
