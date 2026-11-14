"""A document that places a picture still being drawn waits for it, on the
server, and renders once its pictures are drawn: a comic drawn slowly on this
computer still ends as one PDF without the user asking again."""

import asyncio
import threading
import time

import pytest
from sqlalchemy import Engine

from modules.artifacts.models import Artifact
from modules.documents.models import DocumentStatus
from shared.db import create_session_factory
from tests.integration.agent.test_make_image import (  # noqa: F401 - fixtures
    Painter,
    _artifact_id,
    _pictures_in_word,
    _placing,
    _png,
    painter,
)
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.worker.conftest import stub_model  # noqa: F401
from worker.waiting_renders import settle_every_waiting_render

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("stub_model", "model_reads_images"),
]


def _status(engine: Engine, artifact_id: int) -> tuple[DocumentStatus, str | None]:
    with create_session_factory(engine)() as session:
        document = session.get(Artifact, artifact_id).document
        return document.status, document.error_message


async def _ended(engine: Engine, artifact_id: int) -> tuple[DocumentStatus, str | None]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, error = _status(engine, artifact_id)
        if status not in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
            return status, error
        await asyncio.sleep(0.1)
    raise AssertionError(f"artifact {artifact_id} never ended")


@pytest.fixture
def slow(monkeypatch: pytest.MonkeyPatch, painter: Painter) -> Painter:  # noqa: F811
    """The picture call answers queued, and the drawing waits to be let go."""
    monkeypatch.setattr("modules.agent.tool_endpoint.make_image.WAIT_SECONDS", 0.2)
    painter.hold = threading.Event()
    return painter


async def test_a_render_naming_a_picture_still_drawn_waits_and_then_renders(
    tools: ToolEndpoint, studio_worker: None, slow: Painter, engine: Engine
) -> None:
    """Answered at once, not refused; made once the picture is drawn."""
    workspace_id = await tools.workspace()
    queued, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    name = f"image-{_artifact_id(queued)}"

    began = time.monotonic()
    text, is_error = await tools.call(workspace_id, "render_document", _placing(name))

    assert is_error is False, text
    assert time.monotonic() - began < 10
    assert text.startswith("Queued artifact ")
    assert f"renders once {name} is drawn" in text
    render = _artifact_id(text)
    assert _status(engine, render)[0] is DocumentStatus.PENDING

    assert slow.hold is not None
    slow.hold.set()

    assert (await _ended(engine, render))[0] is DocumentStatus.READY
    assert _pictures_in_word(engine, render) == [_png()]


async def test_it_waits_only_for_the_pictures_not_yet_drawn(
    tools: ToolEndpoint,
    studio_worker: None,
    painter: Painter,  # noqa: F811 - the fixture
    engine: Engine,
) -> None:
    """Page one is ready, page two is still drawing: it names only page two."""
    workspace_id = await tools.workspace()
    first, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "Page one", "title": "Page 1"}
    )
    painter.hold = threading.Event()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("modules.agent.tool_endpoint.make_image.WAIT_SECONDS", 0.2)
        second, _ = await tools.call(
            workspace_id, "make_image", {"prompt": "Page two", "title": "Page 2"}
        )
    one, two = f"image-{_artifact_id(first)}", f"image-{_artifact_id(second)}"
    placing = {**_placing(one), "images": [one, two]}

    text, is_error = await tools.call(workspace_id, "render_document", placing)

    assert is_error is False, text
    assert f"renders once {two} is drawn" in text
    assert one not in text.split("renders once", 1)[1]
    painter.hold.set()
    assert (await _ended(engine, _artifact_id(text)))[0] is DocumentStatus.READY


async def test_a_picture_that_fails_fails_the_render_saying_which(
    tools: ToolEndpoint, studio_worker: None, slow: Painter, engine: Engine
) -> None:
    """The agent can draw that page again, or render without it."""
    workspace_id = await tools.workspace()
    queued, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    name = f"image-{_artifact_id(queued)}"
    text, _ = await tools.call(workspace_id, "render_document", _placing(name))

    slow.fail_with = RuntimeError("the provider refused it")
    assert slow.hold is not None
    slow.hold.set()

    status, error = await _ended(engine, _artifact_id(text))
    assert status is DocumentStatus.FAILED
    assert error is not None and f"{name} failed" in error


async def test_a_picture_that_ended_while_the_worker_was_down_is_settled_at_start(
    tools: ToolEndpoint, studio_worker: None, slow: Painter, engine: Engine
) -> None:
    """The job that would have queued it never ran its end."""
    workspace_id = await tools.workspace()
    queued, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    picture = _artifact_id(queued)
    text, _ = await tools.call(
        workspace_id, "render_document", _placing(f"image-{picture}")
    )
    render = _artifact_id(text)
    # As a quit leaves it: the picture's run failed as interrupted, unannounced.
    with create_session_factory(engine)() as session:
        document = session.get(Artifact, picture).document
        document.status = DocumentStatus.FAILED
        document.error_message = "interrupted when the app closed"
        session.commit()

    settle_every_waiting_render()

    status, error = _status(engine, render)
    assert status is DocumentStatus.FAILED
    assert error is not None and f"image-{picture} failed" in error
    assert slow.hold is not None
    slow.hold.set()


async def test_a_picture_cancelled_while_queued_fails_the_render_at_once(
    tools: ToolEndpoint, slow: Painter, engine: Engine
) -> None:
    """A revoked job never runs, so nothing at its end would settle the render."""
    workspace_id = await tools.workspace()
    queued, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    picture = _artifact_id(queued)
    text, _ = await tools.call(
        workspace_id, "render_document", _placing(f"image-{picture}")
    )

    cancelled = await tools.client.post(f"/artifacts/{picture}/cancel")

    assert cancelled.status_code == 200, cancelled.text
    status, error = _status(engine, _artifact_id(text))
    assert status is DocumentStatus.FAILED
    assert error is not None and f"image-{picture} failed" in error
