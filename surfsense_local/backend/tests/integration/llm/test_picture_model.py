"""Which model takes a picture in: the edit model if one is chosen, else the image
model when it can, else none, and then an edit is drawn again from words."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.pictures_in.model import picture_model
from modules.llm.providers import sdcpp
from shared.db import create_session_factory
from tests.integration.llm import conftest
from tests.integration.llm.test_sdcpp_slots import KLEIN, SD15, put_on_disk

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

TAKES_PICTURES = "openai/gpt-image-2.6-flare"
WORDS_ONLY = "recraft/recraft-v4.1-flash"


@pytest.fixture
def image_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """As OpenRouter lists them: what each model takes, and what it returns."""
    monkeypatch.setattr(
        conftest,
        "REMOTE_MODELS",
        [
            *conftest.REMOTE_MODELS,
            {
                "id": TAKES_PICTURES,
                "architecture": {
                    "input_modalities": ["text", "image"],
                    "output_modalities": ["image"],
                },
            },
            {
                "id": WORDS_ONLY,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["image"],
                },
            },
        ],
    )


async def _connect(client: AsyncClient, base_url: str) -> int:
    reply = await client.post(
        "/llm/connections",
        json={
            "label": "Gateway",
            "provider": "openai_compatible",
            "base_url": base_url,
            "api_key": "secret",
        },
    )
    assert reply.status_code == 201, reply.text
    return reply.json()["id"]


async def _choose(
    client: AsyncClient, slot: str, name: str, connection_id: int | None
) -> None:
    provider = "openai_compatible" if connection_id is not None else sdcpp.PROVIDER
    reply = await client.put(
        f"/llm/selection/{slot}",
        json={"provider": provider, "connection_id": connection_id, "name": name},
    )
    assert reply.status_code == 200, reply.text


def _picture_model(engine: Engine):
    with create_session_factory(engine)() as session:
        return picture_model(session)


async def test_an_image_model_that_takes_pictures_edits_with_no_edit_model(
    client: AsyncClient, openai_server: str, image_models: None, engine: Engine
) -> None:
    """Most remote image models take a picture in; none needs a second choice."""
    connection = await _connect(client, openai_server)
    await _choose(client, "image_gen", TAKES_PICTURES, connection)

    chosen = _picture_model(engine)

    assert chosen is not None
    assert chosen.source == "image_model"
    assert chosen.selection.name == TAKES_PICTURES


async def test_an_image_model_that_takes_only_words_has_no_picture_model(
    client: AsyncClient, openai_server: str, image_models: None, engine: Engine
) -> None:
    """Its edits are drawn again from words instead."""
    connection = await _connect(client, openai_server)
    await _choose(client, "image_gen", WORDS_ONLY, connection)

    assert _picture_model(engine) is None


async def test_a_chosen_edit_model_is_used_before_the_image_model(
    client: AsyncClient, openai_server: str, image_models: None, engine: Engine
) -> None:
    """The override, for the user who wants another model for edits."""
    connection = await _connect(client, openai_server)
    await _choose(client, "image_gen", TAKES_PICTURES, connection)
    await _choose(client, "image_edit", TAKES_PICTURES, connection)
    await _choose(client, "image_gen", WORDS_ONLY, connection)

    chosen = _picture_model(engine)

    assert chosen is not None
    assert chosen.source == "edit_model"
    assert chosen.selection.name == TAKES_PICTURES


async def test_another_image_model_does_not_inherit_taking_pictures(
    client: AsyncClient, openai_server: str, image_models: None, engine: Engine
) -> None:
    """What a model takes is its own, not the slot's."""
    connection = await _connect(client, openai_server)
    await _choose(client, "image_gen", TAKES_PICTURES, connection)
    await _choose(client, "image_gen", WORDS_ONLY, connection)

    assert _picture_model(engine) is None


async def test_a_local_image_model_that_edits_takes_pictures(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """FLUX.2 klein's entry names editing; the same files draw and edit."""
    put_on_disk(images_dir, "flux2-klein-4b")
    await _choose(client, "image_gen", KLEIN, None)

    chosen = _picture_model(engine)

    assert chosen is not None
    assert chosen.source == "image_model"
    assert chosen.selection.name == KLEIN


async def test_a_local_image_model_that_only_draws_has_no_picture_model(
    client: AsyncClient, images_dir: Path, engine: Engine
) -> None:
    """Its entry names drawing only."""
    put_on_disk(images_dir, "stable-diffusion-1.5")
    await _choose(client, "image_gen", SD15, None)

    assert _picture_model(engine) is None


async def test_the_app_is_told_which_model_takes_a_picture(
    client: AsyncClient, openai_server: str, image_models: None
) -> None:
    """Studio's Edit says whether a change is an edit or a redraw."""
    connection = await _connect(client, openai_server)

    nothing = (await client.get("/llm/pictures-in")).json()
    await _choose(client, "image_gen", WORDS_ONLY, connection)
    words = (await client.get("/llm/pictures-in")).json()
    await _choose(client, "image_gen", TAKES_PICTURES, connection)
    pictures = (await client.get("/llm/pictures-in")).json()
    await _choose(client, "image_edit", TAKES_PICTURES, connection)
    override = (await client.get("/llm/pictures-in")).json()

    assert nothing == {"source": None}
    assert words == {"source": None}
    assert pictures == {"source": "image_model"}
    assert override == {"source": "edit_model"}
