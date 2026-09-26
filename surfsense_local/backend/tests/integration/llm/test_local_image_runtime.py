"""What Electron runs sd-server on: the chosen image model, only while Studio
needs it and for a few minutes after, so its weights do not sit in memory
beside the chat model all session."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.providers import sdcpp
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

SDXL = "sd_xl_base_1.0_0_Q4_0"
SDXL_FILES = [{"flag": "-m", "path": f"{SDXL}.gguf"}]


async def choose_sdxl(client: AsyncClient, images_dir: Path) -> None:
    """SDXL on disk and chosen for images, as a user leaves it."""
    (images_dir / f"{SDXL}.gguf").write_bytes(b"GGUF")
    chosen = await client.put(
        "/llm/selection/image_gen",
        json={"provider": sdcpp.PROVIDER, "connection_id": None, "name": SDXL},
    )
    assert chosen.status_code == 200, chosen.text


def studio_job(
    engine: Engine, status: DocumentStatus, ago: timedelta, fmt: str = "image"
) -> None:
    """A Studio job of this format, last changed `ago`."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Saturn")
        session.add(workspace)
        session.flush()
        when = datetime.now(UTC) - ago
        document = Document(
            workspace_id=workspace.id,
            title=fmt,
            document_type=DocumentType.ARTIFACT,
            status=status,
            created_at=when,
            updated_at=when,
        )
        session.add(document)
        session.flush()
        session.add(
            Artifact(document_id=document.id, workspace_id=workspace.id, format=fmt)
        )
        session.commit()


async def served(client: AsyncClient) -> list[dict]:
    """The files Electron would start sd-server on; none means stopped."""
    return (await client.get("/llm/image/local/runtime")).json()["files"]


async def test_nothing_runs_while_no_studio_job_needs_an_image(
    client: AsyncClient, images_dir: Path
) -> None:
    """At rest the weights are not in memory at all."""
    await choose_sdxl(client, images_dir)

    assert await served(client) == []


async def test_the_chosen_model_runs_while_an_image_job_does(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """Electron starts it on its next poll, and the job waits for it."""
    await choose_sdxl(client, images_dir)
    studio_job(engine, DocumentStatus.PROCESSING, timedelta(0))

    # Every file on its flag, the model's own size and the flags it pins.
    runtime = (await client.get("/llm/image/local/runtime")).json()
    assert runtime == {
        "files": SDXL_FILES,
        "args": ["-W", "1024", "-H", "1024", "--backend", "vae=cpu"],
    }


async def test_it_stays_up_five_minutes_after_the_last_image_job(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """A second image, or an edit of the first, does not reload the model."""
    await choose_sdxl(client, images_dir)
    studio_job(engine, DocumentStatus.READY, timedelta(minutes=4))

    assert await served(client) == SDXL_FILES


async def test_it_stops_once_five_idle_minutes_have_passed(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """The memory goes back once nobody is making images."""
    await choose_sdxl(client, images_dir)
    studio_job(engine, DocumentStatus.READY, timedelta(minutes=6))

    assert await served(client) == []


async def test_another_studio_job_ends_the_idle_minutes(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """A podcast voices in the memory those weights hold. Measured on 16 GB:
    LongCat Image and the chat model left Kokoro 1.2 GB of the 3.5 GB it needs."""
    await choose_sdxl(client, images_dir)
    studio_job(engine, DocumentStatus.READY, timedelta(minutes=1))
    studio_job(engine, DocumentStatus.PROCESSING, timedelta(0), fmt="podcast")

    assert await served(client) == []


async def test_a_cancelled_image_job_stops_it_at_once(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """sd-server cannot cancel a generation, so stopping it is the cancel."""
    await choose_sdxl(client, images_dir)
    studio_job(engine, DocumentStatus.CANCELLED, timedelta(seconds=10))

    assert await served(client) == []


async def test_a_job_that_needs_no_image_model_does_not_start_it(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """A summary never loads an image model."""
    await choose_sdxl(client, images_dir)
    studio_job(engine, DocumentStatus.PROCESSING, timedelta(0), fmt="summary")

    assert await served(client) == []
