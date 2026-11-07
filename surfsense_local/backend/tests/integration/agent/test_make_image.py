"""The image tool as opencode's MCP client calls it: a picture the agent asked for, kept in Studio."""

import asyncio
import base64
import io
import threading
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from PIL import Image
from sqlalchemy import Engine

from modules.artifacts.local_image_demand import local_image_demand
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers.openai_compatible import NonRetryableImageError
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedImageEdit, ResolvedImageGeneration
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.agent.conftest import declare_image_input
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.worker.conftest import stub_model  # noqa: F401

# The job indexes the picture's prompt; the stub stands in for the embedder.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("stub_model", "model_reads_images"),
]


def _png(colour: str = "teal") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 48), colour).save(out, "PNG")
    return out.getvalue()


class Painter:
    """The image and edit models: records what each was asked."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.edits: list[tuple[str, bytes]] = []
        self.fail_with: Exception | None = None
        self.hold: threading.Event | None = None
        self.gives = GeneratedImage(_png(), "image/png")

    async def generate(self, _model: str, prompt: str) -> GeneratedImage:
        self.prompts.append(prompt)
        if self.fail_with is not None:
            raise self.fail_with
        if self.hold is not None:
            await asyncio.to_thread(self.hold.wait)
        return self.gives

    async def edit(
        self, _model: str, prompt: str, image: GeneratedImage
    ) -> GeneratedImage:
        self.edits.append((prompt, image.content))
        return GeneratedImage(_png("navy"), "image/png")


@pytest.fixture
def painter(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Painter]:
    """An image and an edit model chosen, and no chat model: a drawing never needs one."""
    with create_session_factory(engine)() as session:
        for model_type in (ModelType.IMAGE_GEN, ModelType.IMAGE_EDIT):
            session.add(
                SelectedModel(model_type=model_type, provider="sdcpp", name="m")
            )
        session.commit()
    fake = Painter()
    selection = type("Selection", (), {"provider": "fake", "name": "m"})()
    draws = lambda _session: ResolvedImageGeneration(selection, fake)  # noqa: E731
    edits = lambda _session: ResolvedImageEdit(selection, fake)  # noqa: E731
    monkeypatch.setattr("worker.studio.job.resolve_image_generation", draws)
    monkeypatch.setattr(
        "modules.artifacts.drawn_images.model.resolve_image_generation", draws
    )
    monkeypatch.setattr("worker.studio.job.resolve_image_edit", edits)
    monkeypatch.setattr("modules.artifacts.image_edits.model.resolve_image_edit", edits)
    yield fake
    if fake.hold is not None:
        fake.hold.set()


def _artifact_id(text: str) -> int:
    return int(text.split(",")[0].split(" ")[-1])


def _stored(engine: Engine, artifact_id: int) -> bytes:
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, artifact_id)
        primary = next(f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY)
        return (get_storage_settings().data_dir / primary.storage_key).read_bytes()


async def test_a_picture_is_drawn_from_the_prompt_as_written_with_no_sources(
    tools: ToolEndpoint, studio_worker: None, painter: Painter, engine: Engine
) -> None:
    """No chat model rewrites it: the agent already wrote it, from whatever it read."""
    workspace_id = await tools.workspace()

    text, images, is_error = await tools.call_content(
        workspace_id,
        "make_image",
        {"prompt": "A lighthouse at dusk", "title": "Lighthouse", "style": "image"},
    )

    assert is_error is False, text
    artifact_id = _artifact_id(text)
    assert (
        text.splitlines()[0]
        == f"Rendered artifact {artifact_id}, version 1: Lighthouse"
    )
    assert f"image-{artifact_id}" in text
    assert painter.prompts == ["A lighthouse at dusk"]
    assert _stored(engine, artifact_id) == _png()
    (listed,) = (await tools.client.get(f"/workspaces/{workspace_id}/artifacts")).json()
    assert (listed["format"], listed["status"]) == ("image", "ready")
    assert listed["version"] == {"root_id": artifact_id, "number": 1, "parent_id": None}
    assert listed["image_editable"] is True
    # The model checks its own picture, when it can read one.
    (shown,) = images
    Image.open(io.BytesIO(base64.b64decode(shown["data"]))).verify()


async def test_an_infographic_paints_the_agents_facts_in_studios_style(
    tools: ToolEndpoint, studio_worker: None, painter: Painter
) -> None:
    """The style is Studio's own, so both paths draw alike."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id,
        "make_image",
        {"prompt": "Revenue rose 12%", "title": "Q3", "style": "infographic"},
    )

    assert is_error is False, text
    (painted,) = painter.prompts
    assert "Revenue rose 12%" in painted
    assert "sketchnote" in painted
    (listed,) = (await tools.client.get(f"/workspaces/{workspace_id}/artifacts")).json()
    assert listed["format"] == "infographic"


async def test_a_model_that_cannot_read_images_is_told_it_cannot_see_the_picture(
    tools: ToolEndpoint, studio_worker: None, painter: Painter
) -> None:
    """So it does not describe a picture it never saw."""
    declare_image_input(False)
    workspace_id = await tools.workspace()

    text, images, is_error = await tools.call_content(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    assert is_error is False, text
    assert images == []
    assert "cannot see it" in text


async def test_editing_a_chats_picture_makes_its_next_version_in_that_chat(
    tools: ToolEndpoint, studio_worker: None, painter: Painter, engine: Engine
) -> None:
    """The instruction goes to the edit model as written, and the picture keeps its title."""
    workspace_id = await tools.workspace()
    first, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    root = _artifact_id(first)

    text, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": "Make it night", "artifact_id": root}
    )

    assert is_error is False, text
    second = _artifact_id(text)
    assert text.splitlines()[0] == f"Rendered artifact {second}, version 2: Boat"
    assert f"image-{second}" in text
    assert painter.edits == [("Make it night", _png())]
    assert _stored(engine, second) == _png("navy")
    with create_session_factory(engine)() as session:
        assert session.get(Artifact, second).chat_thread_id == tools.default_thread(
            workspace_id
        )


async def test_another_chats_picture_cannot_be_edited(
    tools: ToolEndpoint, studio_worker: None, painter: Painter
) -> None:
    """The name of what a chat may touch is one it was given itself."""
    workspace_id = await tools.workspace()
    first, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    text, is_error = await tools.call(
        workspace_id,
        "make_image",
        {"prompt": "Make it night", "artifact_id": _artifact_id(first)},
        thread=tools.thread(workspace_id),
    )

    assert is_error is True
    assert "made no picture" in text
    assert painter.edits == []


async def test_a_workspace_with_no_image_model_is_told_what_it_needs(
    tools: ToolEndpoint,
) -> None:
    """In a sentence the agent can pass on, with nothing left pending."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    assert is_error is True
    assert "Needs an image model." in text
    assert (
        await tools.client.get(f"/workspaces/{workspace_id}/artifacts")
    ).json() == []


async def test_the_same_title_again_is_refused_so_a_retry_does_not_bill_twice(
    tools: ToolEndpoint, studio_worker: None, painter: Painter
) -> None:
    """A model that lost track of its first call would pay for a second picture."""
    workspace_id = await tools.workspace()
    first, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    text, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat again", "title": "boat"}
    )

    assert is_error is True
    assert f"pass artifact_id {_artifact_id(first)}" in text
    assert painter.prompts == ["A boat"]


@pytest.mark.parametrize(
    "arguments, words",
    [
        ({"title": "Boat"}, "Give the prompt"),
        ({"prompt": "A boat"}, "Give the picture a title"),
        ({"prompt": "x" * 2001, "title": "Boat"}, "at most 2,000 characters"),
        ({"prompt": "A boat", "title": "Boat", "style": "mural"}, "style must be"),
    ],
)
async def test_a_call_missing_something_says_what_to_fix(
    tools: ToolEndpoint, arguments: dict, words: str
) -> None:
    """A small model may leave arguments out; the refusal names the one to fix."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(workspace_id, "make_image", arguments)

    assert is_error is True
    assert words in text


@pytest.mark.parametrize(
    "failure", [NonRetryableImageError("HTTP 400"), RuntimeError("the model hung up")]
)
async def test_a_failed_picture_is_reported_and_never_asked_for_again(
    tools: ToolEndpoint, studio_worker: None, painter: Painter, failure: Exception
) -> None:
    """Each try may be billed, so the worker's own retry stays out of it."""
    painter.fail_with = failure
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    assert is_error is True
    assert str(failure) in text
    assert painter.prompts == ["A boat"]
    (listed,) = (await tools.client.get(f"/workspaces/{workspace_id}/artifacts")).json()
    assert listed["status"] == "failed"


async def test_three_failed_pictures_stop_the_turn(
    tools: ToolEndpoint, studio_worker: None, painter: Painter
) -> None:
    """Small models retry without end; each try here may be billed."""
    painter.fail_with = NonRetryableImageError("HTTP 500")
    workspace_id = await tools.workspace()

    for title in ("One", "Two", "Three"):
        await tools.call(workspace_id, "make_image", {"prompt": "x", "title": title})
    text, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": "x", "title": "Four"}
    )

    assert is_error is True
    assert "3 pictures failed" in text
    assert len(painter.prompts) == 3


async def test_a_slow_picture_answers_queued_with_the_name_it_will_have(
    tools: ToolEndpoint,
    studio_worker: None,
    painter: Painter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local picture on a processor outlasts the tool call's hard limit."""
    monkeypatch.setattr("modules.agent.tool_endpoint.make_image.WAIT_SECONDS", 0.2)
    painter.hold = threading.Event()
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    assert is_error is False, text
    artifact_id = _artifact_id(text)
    assert text.splitlines()[0] == f"Queued artifact {artifact_id}, version 1: Boat"
    assert f"image-{artifact_id}" in text
    assert "Do not make it again" in text


async def test_regenerating_paints_the_same_prompt_with_no_chat_model(
    tools: ToolEndpoint, studio_worker: None, painter: Painter, engine: Engine
) -> None:
    """A drawing has no sources to replay and no writer to ask."""
    workspace_id = await tools.workspace()
    first, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    artifact_id = _artifact_id(first)

    reply = await tools.client.post(f"/artifacts/{artifact_id}/regenerate")

    assert reply.status_code == 202, reply.text
    for _ in range(100):
        if len(painter.prompts) == 2:
            break
        await asyncio.sleep(0.05)
    assert painter.prompts == ["A boat", "A boat"]


async def test_the_studio_tool_sends_a_picture_to_the_image_tool(
    tools: ToolEndpoint,
) -> None:
    """One way to make a picture: Studio's draft takes sources, and hands nothing back."""
    workspace_id = await tools.workspace()

    listed = await tools.request(workspace_id, "tools/list")
    studio = next(
        tool for tool in listed["result"]["tools"] if tool["name"] == "create_artifact"
    )
    text, is_error = await tools.call(
        workspace_id, "create_artifact", {"format": "image", "source_ids": [1]}
    )

    assert not {"image", "infographic"} & set(
        studio["inputSchema"]["properties"]["format"]["enum"]
    )
    assert is_error is True
    assert "surfsense_make_image" in text


# Fails unless what it is handed is really a PNG, as IMAGES_DIR promises.
WORD_WITH_PICTURE = """\
import os
from docx import Document
from PIL import Image

path = os.path.join(os.environ["IMAGES_DIR"], "{name}.png")
assert Image.open(path).format == "PNG"
document = Document()
document.add_paragraph("With a picture.")
document.add_picture(path)
document.save(os.environ["OUTPUT_PATH"])
"""


def _placing(name: str) -> dict[str, object]:
    return {
        "title": "Report",
        "format": "docx",
        "script": WORD_WITH_PICTURE.format(name=name),
        "images": [name],
    }


def _pictures_in_word(engine: Engine, artifact_id: int) -> list[bytes]:
    with zipfile.ZipFile(io.BytesIO(_stored(engine, artifact_id))) as word:
        return [
            word.read(name)
            for name in word.namelist()
            if name.startswith("word/media/")
        ]


async def test_a_document_places_a_picture_by_its_name(
    tools: ToolEndpoint, studio_worker: None, painter: Painter, engine: Engine
) -> None:
    """Named as the tool gave it, the picture lands in the Word file byte for byte."""
    workspace_id = await tools.workspace()
    drawn, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    text, is_error = await tools.call(
        workspace_id, "render_document", _placing(f"image-{_artifact_id(drawn)}")
    )

    assert is_error is False, text
    assert _pictures_in_word(engine, _artifact_id(text)) == [_png()]


async def test_a_picture_the_model_gave_as_jpeg_is_placed_as_a_png(
    tools: ToolEndpoint, studio_worker: None, painter: Painter, engine: Engine
) -> None:
    """Remote models answer in other formats; a script is promised `<name>.png`."""
    out = io.BytesIO()
    Image.new("RGB", (64, 48), "teal").save(out, "JPEG")
    painter.gives = GeneratedImage(out.getvalue(), "image/jpeg")
    workspace_id = await tools.workspace()
    drawn, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    text, is_error = await tools.call(
        workspace_id, "render_document", _placing(f"image-{_artifact_id(drawn)}")
    )

    assert is_error is False, text
    (placed,) = _pictures_in_word(engine, _artifact_id(text))
    assert Image.open(io.BytesIO(placed)).format == "PNG"


async def test_a_copy_the_agent_overwrote_is_not_what_gets_placed(
    tools: ToolEndpoint, studio_worker: None, painter: Painter, engine: Engine
) -> None:
    """Its outputs folder is the agent's to write; the kept picture is the truth."""
    workspace_id = await tools.workspace()
    drawn, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    name = f"image-{_artifact_id(drawn)}"
    await tools.call(workspace_id, "render_document", _placing(name))
    copy = tools.folder(workspace_id) / "outputs" / "images" / f"{name}.png"
    assert copy.read_bytes() == _png()
    copy.write_bytes(_png("red"))

    text, is_error = await tools.call(
        workspace_id, "render_document", {**_placing(name), "title": "Second"}
    )

    assert is_error is False, text
    assert _pictures_in_word(engine, _artifact_id(text)) == [_png()]


async def test_a_picture_still_being_drawn_is_refused_saying_so(
    tools: ToolEndpoint,
    studio_worker: None,
    painter: Painter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent tells the user, rather than reading it as a wrong name."""
    monkeypatch.setattr("modules.agent.tool_endpoint.make_image.WAIT_SECONDS", 0.2)
    painter.hold = threading.Event()
    workspace_id = await tools.workspace()
    queued, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    text, is_error = await tools.call(
        workspace_id, "render_document", _placing(f"image-{_artifact_id(queued)}")
    )

    assert is_error is True
    assert "still being drawn" in text


async def test_another_chats_picture_cannot_be_placed(
    tools: ToolEndpoint, studio_worker: None, painter: Painter
) -> None:
    """As a chart's name is, a picture's is its own chat's."""
    workspace_id = await tools.workspace()
    drawn, _ = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )

    text, is_error = await tools.call(
        workspace_id,
        "render_document",
        _placing(f"image-{_artifact_id(drawn)}"),
        thread=tools.thread(workspace_id),
    )

    assert is_error is True
    assert "This chat has no picture named" in text


async def test_a_format_a_document_cannot_place_says_so_and_gives_no_name(
    tools: ToolEndpoint, studio_worker: None, painter: Painter
) -> None:
    """A remote model may answer in SVG, which a script is not promised."""
    painter.gives = GeneratedImage(b"<svg/>", "image/svg+xml")
    workspace_id = await tools.workspace()

    drawn, is_error = await tools.call(
        workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"}
    )
    placed, placed_error = await tools.call(
        workspace_id, "render_document", _placing(f"image-{_artifact_id(drawn)}")
    )

    assert is_error is False, drawn
    assert "documents cannot place" in drawn
    assert "Its name is" not in drawn
    assert placed_error is True
    assert "This chat has no picture named" in placed


async def test_a_picture_being_drawn_asks_for_the_local_image_server(
    tools: ToolEndpoint,
    studio_worker: None,
    painter: Painter,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Electron starts sd-server on this answer; the fake painter runs nothing local."""
    monkeypatch.setattr("modules.agent.tool_endpoint.make_image.WAIT_SECONDS", 0.2)
    painter.hold = threading.Event()
    workspace_id = await tools.workspace()

    await tools.call(workspace_id, "make_image", {"prompt": "A boat", "title": "Boat"})

    with create_session_factory(engine)() as session:
        assert local_image_demand(session, datetime.now(UTC)) is ModelType.IMAGE_GEN
