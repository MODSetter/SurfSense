"""Image models in the one local catalog, offered by sd.cpp."""

import json

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

IMAGE_IDS = {
    "flux2-klein-4b",
    "z-image-turbo",
    "ernie-image-turbo",
    "stable-diffusion-1.5",
    "sdxl-base-1.0",
}


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


async def test_a_second_install_waits_its_turn_instead_of_failing(
    client: AsyncClient, images_dir, fake_hub
) -> None:
    """Onboarding moves on while a download runs, so a second model is chosen
    before the first lands; one download at a time, in order."""
    import asyncio

    from modules.llm.catalog.local.dependencies import get_local_catalog

    body = (await client.get("/llm/catalog/local")).json()
    build = image_rows(body)["stable-diffusion-1.5"]["builds"][0]
    ahead = get_local_catalog().install_lock()
    await ahead.acquire()

    second = asyncio.create_task(
        client.post("/llm/install", json={"catalog_id": build["catalog_id"]})
    )
    await asyncio.sleep(0.2)
    assert not second.done()
    ahead.release()
    reply = await second

    events = [json.loads(line) for line in reply.text.splitlines()]
    assert reply.status_code == 200
    assert events[0]["type"] == "queued"
    assert events[-1]["type"] == "complete", events[-1]


async def test_a_download_the_disk_cannot_hold_is_refused_before_it_starts(
    client: AsyncClient, images_dir, fake_hub, monkeypatch
) -> None:
    """Said before any byte moves, with how much room it needs."""
    import shutil

    from modules.llm.catalog.local.install import disk_room

    monkeypatch.setattr(
        disk_room,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(10**12, 10**12, 10**6),
    )
    body = (await client.get("/llm/catalog/local")).json()
    build = image_rows(body)["stable-diffusion-1.5"]["builds"][0]

    reply = await client.post("/llm/install", json={"catalog_id": build["catalog_id"]})

    events = [json.loads(line) for line in reply.text.splitlines()]
    assert events[-1]["type"] == "error"
    assert "4.1 GB free" in events[-1]["message"]
    assert not (images_dir / "v1-5-pruned_Q4_0.gguf").exists()
