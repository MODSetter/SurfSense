"""Image sources that retrieval finds, handed to a model that can see them."""

import io
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image as Pillow
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentType
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.chat.conftest import set_sees
from tests.integration.chat.test_chat import _open_thread
from tests.integration.chat.test_images import image_parts, send
from worker.ingestion import parsing, run

pytestmark = pytest.mark.integration

RECEIPT = "Receipt from the harbour cafe: two coffees and a croissant."


@pytest.fixture
def ocr_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docling's OCR stands in as fixed text, so indexing an image stays fast."""
    monkeypatch.setattr(parsing, "_markdown_from", lambda _path: RECEIPT)


def seed_image_sources(engine: Engine, count: int) -> tuple[int, list[Path]]:
    """A workspace of indexed image uploads and a chosen chat model."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Receipts")
        session.add(workspace)
        session.flush()
        documents = []
        for n in range(count):
            document = Document(
                workspace_id=workspace.id,
                title=f"receipt-{n}.png",
                document_type=DocumentType.FILE,
                dedup_key=f"receipt-{n}",
                document_metadata={"mime_type": "image/png", "suffix": ".png"},
            )
            session.add(document)
            documents.append(document)
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="llamacpp",
                name="Qwen3-1.7B-Q4_K_M",
            )
        )
        session.flush()
        files = []
        for n, document in enumerate(documents):
            folder = get_storage_settings().document_dir(workspace.id, document.id)
            folder.mkdir(parents=True)
            path = folder / f"receipt-{n}.png"
            out = io.BytesIO()
            Pillow.new("RGB", (80, 60), "white").save(out, format="PNG")
            path.write_bytes(out.getvalue())
            files.append(path)
        session.commit()
        workspace_id, ids = workspace.id, [d.id for d in documents]
    for document_id in ids:
        run(document_id)
    return workspace_id, files


async def last_question(client: AsyncClient, workspace_id: int, sent: list[dict]):
    """Ask about the receipts and return the user turn the model received."""
    thread_id = await _open_thread(client, workspace_id)
    status, _ = await send(client, thread_id, "what did I buy at the cafe?", [])
    assert status == 200
    return sent[-1]["messages"][-1]


async def test_a_model_that_sees_gets_the_retrieved_image_itself(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
    ocr_text: None,
) -> None:
    """OCR keeps the words; the picture keeps what OCR drops."""
    set_sees(True)
    workspace_id, _ = seed_image_sources(engine, 1)

    asked = await last_question(client, workspace_id, llamacpp_server)

    assert len(image_parts(asked)) == 1


async def test_a_model_that_cannot_see_gets_the_text_alone(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
    ocr_text: None,
) -> None:
    """Exactly today's request."""
    workspace_id, _ = seed_image_sources(engine, 1)

    asked = await last_question(client, workspace_id, llamacpp_server)

    assert asked == {"role": "user", "content": "what did I buy at the cafe?"}


async def test_at_most_two_image_sources_ride_along(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
    ocr_text: None,
) -> None:
    """The highest ranked, so a pile of screenshots cannot fill the window."""
    set_sees(True)
    workspace_id, _ = seed_image_sources(engine, 3)

    asked = await last_question(client, workspace_id, llamacpp_server)

    assert len(image_parts(asked)) == 2


async def test_a_missing_original_leaves_the_turn_as_text(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
    ocr_text: None,
) -> None:
    """Search still has its words; only the picture is gone."""
    set_sees(True)
    workspace_id, files = seed_image_sources(engine, 1)
    files[0].unlink()

    asked = await last_question(client, workspace_id, llamacpp_server)

    assert image_parts(asked) == []
    assert "what did I buy" in str(asked["content"])


async def test_sources_are_never_stored_with_the_turn(
    client: AsyncClient,
    engine: Engine,
    real_model: object,
    llamacpp_server: list[dict],
    data_dir: Path,
    ocr_text: None,
) -> None:
    """They come from sources, not the person, and are fetched again when found."""
    set_sees(True)
    workspace_id, _ = seed_image_sources(engine, 1)
    thread_id = await _open_thread(client, workspace_id)

    await send(client, thread_id, "what did I buy at the cafe?", [])

    user, _ = (await client.get(f"/chat/threads/{thread_id}/messages")).json()
    assert "images" not in user["content"]
