"""Image models in the one local catalog, offered by sd.cpp."""

import json

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

IMAGE_IDS = {"stable-diffusion-1.5", "sdxl-base-1.0", "sdxl-turbo"}


def image_rows(body: dict) -> dict[str, dict]:
    """The rows sd.cpp offered, by id."""
    return {r["id"]: r for r in body["rows"] if r["engine"] == "sdcpp"}


async def test_image_models_are_rows_with_no_fit_claim(
    client: AsyncClient, images_dir
) -> None:
    """Runnable, downloadable, and silent about this machine."""
    body = (await client.get("/llm/catalog/local")).json()

    rows = image_rows(body)
    assert set(rows) == IMAGE_IDS
    sd15 = rows["stable-diffusion-1.5"]
    assert sd15["types"] == ["image_gen"]
    assert sd15["selectable_for"] == ["image_gen"]
    assert sd15["runnable"] and not sd15["recommended"]
    assert sd15["default_quantization"] == "Q4_0"
    assert sd15["lead"] == {"quantization": "Q4_0", "why": "default"}
    (build,) = sd15["builds"]
    assert build["fit"] is None and build["badge"] is None
    assert build["can_install"]


async def test_a_build_with_no_sd_server_offers_no_image_rows(
    client: AsyncClient,
) -> None:
    """No images folder means Electron staged no sd-server for this host."""
    body = (await client.get("/llm/catalog/local")).json()

    assert not image_rows(body)


async def test_an_image_build_installs_into_its_folder_and_is_selected(
    client: AsyncClient, images_dir, fake_hub
) -> None:
    """One install stream for every engine; an image build ends as the image
    selection, with nothing for llama-server to restart over."""
    body = (await client.get("/llm/catalog/local")).json()
    build = image_rows(body)["stable-diffusion-1.5"]["builds"][0]

    reply = await client.post(
        "/llm/install", json={"catalog_id": build["catalog_id"], "select": True}
    )

    events = [json.loads(line) for line in reply.text.splitlines()]
    assert events[-1]["type"] == "complete", events[-1]
    assert not any(e["type"] == "preparing" for e in events)
    assert (images_dir / "v1-5-pruned_Q4_0.gguf").exists()
    selection = (await client.get("/llm/selection/image_gen")).json()
    assert (selection["provider"], selection["name"]) == ("sdcpp", "v1-5-pruned_Q4_0")


async def test_deleting_an_image_model_from_the_catalog_clears_its_selection(
    client: AsyncClient, images_dir
) -> None:
    """The screen's one Delete covers every engine, as it does a chat model."""
    (images_dir / "v1-5-pruned_Q4_0.gguf").write_bytes(b"GGUF")
    await client.put(
        "/llm/selection/image_gen",
        json={"provider": "sdcpp", "connection_id": None, "name": "v1-5-pruned_Q4_0"},
    )

    reply = await client.delete("/llm/models/v1-5-pruned_Q4_0")

    assert reply.status_code == 200, reply.text
    assert reply.json()["selection_cleared"] is True
    assert not (images_dir / "v1-5-pruned_Q4_0.gguf").exists()
    assert (await client.get("/llm/selection/image_gen")).status_code == 404
