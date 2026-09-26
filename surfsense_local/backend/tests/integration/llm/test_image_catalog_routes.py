"""Image models in the one local catalog, offered by sd.cpp."""

import pytest
from httpx import AsyncClient

from tests.integration.llm.installs import install_to_end, wait_for_end

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

IMAGE_IDS = {
    "flux2-klein-4b",
    "z-image-turbo",
    "ernie-image-turbo",
    "longcat-image",
    "stable-diffusion-1.5",
    "sdxl-base-1.0",
}


def image_rows(body: dict) -> dict[str, dict]:
    """The image rows sd.cpp offered, by id; its video rows are beside them."""
    return {
        r["id"]: r
        for r in body["rows"]
        if r["engine"] == "sdcpp" and "image_gen" in r["selectable_for"]
    }


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

    job = await install_to_end(client, catalog_id=build["catalog_id"], select=True)

    assert job["event"]["type"] == "complete", job
    assert job["label"] == "Stable Diffusion 1.5 Q4_0"
    assert job["model_types"] == ["image_gen"]
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

    second = await client.post(
        "/llm/installs", json={"catalog_id": build["catalog_id"]}
    )
    await asyncio.sleep(0.2)

    assert second.status_code == 202
    waiting = (await client.get(f"/llm/installs/{second.json()['id']}")).json()
    assert waiting["event"]["type"] == "queued"
    ahead.release()
    job = await wait_for_end(client, second.json()["id"])
    assert job["event"]["type"] == "complete", job


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

    job = await install_to_end(client, catalog_id=build["catalog_id"])

    assert job["event"]["type"] == "error"
    assert "4.1 GB free" in job["event"]["message"]
    assert not (images_dir / "v1-5-pruned_Q4_0.gguf").exists()
