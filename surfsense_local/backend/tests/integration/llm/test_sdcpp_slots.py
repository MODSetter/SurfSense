"""sd.cpp fills three slots, each with the models whose entry says so: an image
model that edits too fills the editing slot from the same files, and a video
model the video slot."""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.llm.catalog.local.engines.sdcpp.images_folder.landing import landing
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.providers import sdcpp

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

KLEIN = "flux-2-klein-4b-Q4_0"
SD15 = "v1-5-pruned_Q4_0"


def put_on_disk(images_dir: Path, model_id: str) -> None:
    """Every file of the curated model's default build, where it lands."""
    model = next(m for m in load_local_manifest().models if m.id == model_id)
    for file in model.as_builds()[0].files:
        (images_dir / landing(file)).parent.mkdir(parents=True, exist_ok=True)
        (images_dir / landing(file)).write_bytes(b"x")


async def choose(client: AsyncClient, slot: str, name: str) -> int:
    """The status of choosing this local image model for this slot."""
    reply = await client.put(
        f"/llm/selection/{slot}",
        json={"provider": sdcpp.PROVIDER, "connection_id": None, "name": name},
    )
    return reply.status_code


async def test_flux2_klein_fills_the_image_editing_slot(
    client: AsyncClient, images_dir: Path
) -> None:
    """The same files it generates with; nothing more to download."""
    put_on_disk(images_dir, "flux2-klein-4b")

    assert await choose(client, "image_edit", KLEIN) == 200


async def test_a_model_that_only_generates_is_refused_for_editing(
    client: AsyncClient, images_dir: Path
) -> None:
    """Its entry names generating only."""
    put_on_disk(images_dir, "stable-diffusion-1.5")

    assert await choose(client, "image_edit", SD15) == 422


async def test_a_build_says_which_slots_chose_it(
    client: AsyncClient, images_dir: Path
) -> None:
    """Settings' image and editing sections each mark it by their own slot."""
    put_on_disk(images_dir, "flux2-klein-4b")
    put_on_disk(images_dir, "stable-diffusion-1.5")
    await choose(client, "image_gen", SD15)
    await choose(client, "image_edit", KLEIN)

    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    builds = {
        b["installed_as"]: b for r in rows for b in r["builds"] if b["installed_as"]
    }

    assert builds[KLEIN]["selected_for"] == ["image_edit"]
    assert builds[SD15]["selected_for"] == ["image_gen"]


async def test_deleting_a_model_clears_every_slot_it_filled(
    client: AsyncClient, images_dir: Path
) -> None:
    """Neither slot is left naming files that are gone."""
    put_on_disk(images_dir, "flux2-klein-4b")
    await choose(client, "image_gen", KLEIN)
    await choose(client, "image_edit", KLEIN)

    deleted = await client.delete(f"/llm/models/{KLEIN}")

    assert deleted.json()["selection_cleared"] is True
    assert (await client.get("/llm/selection/image_gen")).status_code == 404
    assert (await client.get("/llm/selection/image_edit")).status_code == 404


async def test_an_install_can_fill_the_editing_slot(
    client: AsyncClient, images_dir: Path, fake_hub
) -> None:
    """Onboarding's editing step downloads straight into its own slot."""
    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    klein = next(r for r in rows if r["id"] == "flux2-klein-4b")

    reply = await client.post(
        "/llm/install",
        json={
            "catalog_id": klein["builds"][0]["catalog_id"],
            "select": True,
            "model_type": "image_edit",
        },
    )

    events = [json.loads(line) for line in reply.text.splitlines()]
    assert events[-1]["type"] == "complete", events[-1]
    assert events[-1]["selection"]["model_type"] == "image_edit"
    assert (await client.get("/llm/selection/image_gen")).status_code == 404


async def test_a_video_model_fills_the_video_slot(
    client: AsyncClient, images_dir: Path
) -> None:
    """Wan's entry has a video block, so video is what it is for."""
    put_on_disk(images_dir, "wan2.1-t2v-1.3b")

    assert await choose(client, "video_gen", "Wan2.1-T2V-1.3B-Q8_0") == 200
    assert await choose(client, "image_gen", "Wan2.1-T2V-1.3B-Q8_0") == 422


async def test_an_image_model_is_refused_for_video(
    client: AsyncClient, images_dir: Path
) -> None:
    """FLUX.2 klein makes and edits images; it makes no clip."""
    put_on_disk(images_dir, "flux2-klein-4b")

    assert await choose(client, "video_gen", KLEIN) == 422
