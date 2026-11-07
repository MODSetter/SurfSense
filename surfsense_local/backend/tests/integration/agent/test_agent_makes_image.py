"""The agent drawing a picture and placing it, through real opencode with its model scripted."""

import io
import json
import zipfile

import pytest
from PIL import Image
from sqlalchemy import Engine

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedImageGeneration
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_documents import _finished, call
from tests.integration.agent.test_agent_threads import open_thread, send
from tests.integration.worker.conftest import stub_model  # noqa: F401

# The job indexes what was drawn; the stub stands in for the embedder.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

WORD_WITH_PICTURE = """\
import os
from docx import Document

document = Document()
document.add_picture(os.path.join(os.environ["IMAGES_DIR"], "image-1.png"))
document.save(os.environ["OUTPUT_PATH"])
"""


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 48), "teal").save(out, "PNG")
    return out.getvalue()


class Painter:
    async def generate(self, _model: str, prompt: str) -> GeneratedImage:
        self.prompt = prompt
        return GeneratedImage(_png(), "image/png")


async def test_the_agent_draws_a_picture_and_places_it_in_a_document(
    agent_api: AgentAPI,
    studio_worker: None,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One request, from the model's tool call to a Word file holding the picture."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(model_type=ModelType.IMAGE_GEN, provider="sdcpp", name="m")
        )
        session.commit()
    painter = Painter()
    selection = type("Selection", (), {"provider": "fake", "name": "m"})()
    draws = lambda _session: ResolvedImageGeneration(selection, painter)  # noqa: E731
    monkeypatch.setattr("worker.studio.job.resolve_image_generation", draws)
    monkeypatch.setattr(
        "modules.artifacts.drawn_images.model.resolve_image_generation", draws
    )
    agent_api.model.replies = [
        call(
            "surfsense_make_image",
            {"prompt": "One comic page of a boy on a broom", "title": "Comic page"},
        ),
        call(
            "surfsense_render_document",
            {
                "title": "Comic",
                "format": "docx",
                "script": WORD_WITH_PICTURE,
                "images": ["image-1"],
            },
        ),
        ("text", "Your comic is ready."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Make a comic page and put it in Word")

    drawn = _finished(frames, "surfsense_make_image")
    assert drawn["status"] == "completed", drawn
    assert drawn["artifact"] == {
        "id": 1,
        "title": "Comic page",
        "version": 1,
        "created": True,
    }
    rendered = _finished(frames, "surfsense_render_document")
    assert rendered["status"] == "completed", rendered
    assert painter.prompt == "One comic page of a boy on a broom"
    # The model is told the name it placed the picture by.
    assert "image-1" in json.dumps(agent_api.model.requests[1]["messages"])
    with create_session_factory(engine)() as session:
        word = session.get(Artifact, rendered["artifact"]["id"])
        primary = next(f for f in word.files if f.role is ArtifactFileRole.PRIMARY)
        data = (get_storage_settings().data_dir / primary.storage_key).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as document:
        (picture,) = [n for n in document.namelist() if n.startswith("word/media/")]
        assert document.read(picture) == _png()
