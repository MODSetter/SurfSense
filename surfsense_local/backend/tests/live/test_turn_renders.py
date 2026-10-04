"""What a turn rendered and which page previews the agent opened, read from its frames."""

from pathlib import Path

import pytest

from tests.live.turn_renders import (
    Version,
    pages_left_unread,
    previews_opened,
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
