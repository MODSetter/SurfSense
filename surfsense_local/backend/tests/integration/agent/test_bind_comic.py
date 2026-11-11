"""The agent binds the pages it drew into a comic: one Studio artifact, a PDF in reading order."""

import asyncio
import io
import threading
import time
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader
from sqlalchemy import Engine

from modules.artifacts.local_image_demand import local_image_demand
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import DocumentStatus
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.agent.test_make_image import (  # noqa: F401 - fixtures
    Painter,
    _artifact_id,
    painter,
)
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.worker.conftest import stub_model  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("stub_model", "model_reads_images", "studio_worker"),
]


async def _picture(tools: ToolEndpoint, workspace_id: int, title: str) -> str:
    text, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": f"A page: {title}", "title": title}
    )
    assert is_error is False, text
    return f"image-{_artifact_id(text)}"


def _comic(engine: Engine, artifact_id: int) -> tuple[str, dict, PdfReader]:
    """Its format, its metadata and its PDF."""
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        assert artifact is not None
        primary = next(f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY)
        pdf = (get_storage_settings().data_dir / primary.storage_key).read_bytes()
        return (
            artifact.format,
            dict(artifact.artifact_metadata or {}),
            PdfReader(io.BytesIO(pdf)),
        )


async def _ended(engine: Engine, artifact_id: int) -> DocumentStatus:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with create_session_factory(engine)() as session:
            status = session.get(Artifact, artifact_id).document.status
        if status not in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
            return status
        await asyncio.sleep(0.1)
    raise AssertionError(f"artifact {artifact_id} never ended")


async def test_the_pages_become_one_comic_in_studio(
    tools: ToolEndpoint,
    painter: Painter,  # noqa: F811
    engine: Engine,
) -> None:
    """One artifact in Studio, its pages in the order given, read as asked."""
    workspace_id = await tools.workspace()
    first = await _picture(tools, workspace_id, "Cat · page 1")
    second = await _picture(tools, workspace_id, "Cat · page 2")

    text, is_error = await tools.call(
        workspace_id,
        "bind_comic",
        {
            "title": "The Lighthouse Cat",
            "pages": [
                {"image": first},
                {"image": second, "lines": ["NORA: The bulb is broken!"]},
            ],
            "direction": "rtl",
        },
    )

    assert is_error is False, text
    comic_id = _artifact_id(text)
    assert text.splitlines()[0] == (
        f"Rendered artifact {comic_id}, version 1: The Lighthouse Cat"
    )
    assert "2 pages" in text
    format, _, pdf = _comic(engine, comic_id)
    assert format == "comic"
    assert len(pdf.pages) == 2
    assert "NORA: The bulb is broken!" in pdf.pages[1].extract_text()
    assert pdf.trailer["/Root"]["/ViewerPreferences"]["/Direction"] == "/R2L"
    listed = (await tools.client.get(f"/workspaces/{workspace_id}/artifacts")).json()
    row = next(a for a in listed if a["id"] == comic_id)
    assert (row["format"], row["status"]) == ("comic", "ready")


async def test_binding_again_with_its_id_makes_the_comics_next_version(
    tools: ToolEndpoint,
    painter: Painter,  # noqa: F811
    engine: Engine,
) -> None:
    """A page is changed with make_image, then the comic is bound again around it."""
    workspace_id = await tools.workspace()
    first = await _picture(tools, workspace_id, "Cat · page 1")
    made, _ = await tools.call(
        workspace_id, "bind_comic", {"title": "Cat", "pages": [{"image": first}]}
    )
    second = await _picture(tools, workspace_id, "Cat · page 2")

    text, is_error = await tools.call(
        workspace_id,
        "bind_comic",
        {
            "title": "Cat",
            "pages": [{"image": first}, {"image": second}],
            "artifact_id": _artifact_id(made),
        },
    )

    assert is_error is False, text
    assert ", version 2: Cat" in text.splitlines()[0]
    _, metadata, pdf = _comic(engine, _artifact_id(text))
    assert metadata["version"]["parent"] == _artifact_id(made)
    assert len(pdf.pages) == 2


async def test_a_page_still_being_drawn_is_waited_for(
    tools: ToolEndpoint,
    painter: Painter,  # noqa: F811
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A comic drawn slowly on this computer still ends as one PDF, without asking again."""
    workspace_id = await tools.workspace()
    first = await _picture(tools, workspace_id, "Cat · page 1")
    monkeypatch.setattr("modules.agent.tool_endpoint.make_image.WAIT_SECONDS", 0.2)
    painter.hold = threading.Event()
    second = await _picture(tools, workspace_id, "Cat · page 2")

    text, is_error = await tools.call(
        workspace_id,
        "bind_comic",
        {"title": "Cat", "pages": [{"image": first}, {"image": second}]},
    )

    assert is_error is False, text
    assert text.startswith("Queued artifact ")
    assert f"renders once {second} is drawn" in text
    painter.hold.set()
    assert await _ended(engine, _artifact_id(text)) is DocumentStatus.READY


@pytest.mark.parametrize(
    "arguments, words",
    [
        ({"pages": [{"image": "image-1"}]}, "Give the comic a title"),
        ({"title": "Cat", "pages": []}, "Give the pages"),
        ({"title": "Cat", "pages": [{"image": "image-999"}]}, "no picture named"),
        (
            {"title": "Cat", "pages": [{"image": "image-1"}], "layout": "spiral"},
            "layout must be one of: pages, scroll",
        ),
        (
            {"title": "Cat", "pages": [{"image": "image-1"}] * 13},
            "at most 12 pages",
        ),
    ],
)
async def test_a_call_missing_something_says_what_to_fix(
    tools: ToolEndpoint, arguments: dict, words: str
) -> None:
    """A small model may leave arguments out; the refusal names the one to fix."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(workspace_id, "bind_comic", arguments)

    assert is_error is True
    assert words in text


async def test_binding_a_comic_does_not_start_the_local_image_model(
    tools: ToolEndpoint,
    painter: Painter,  # noqa: F811
    engine: Engine,
) -> None:
    """Binding draws nothing: the image model's memory stays the chat model's."""
    workspace_id = await tools.workspace()
    first = await _picture(tools, workspace_id, "Cat · page 1")
    made, _ = await tools.call(
        workspace_id, "bind_comic", {"title": "Cat", "pages": [{"image": first}]}
    )
    with create_session_factory(engine)() as session:
        comic = session.get(Artifact, _artifact_id(made))
        comic.document.status = DocumentStatus.PROCESSING
        session.commit()

        assert local_image_demand(session, datetime.now(UTC)) is None

