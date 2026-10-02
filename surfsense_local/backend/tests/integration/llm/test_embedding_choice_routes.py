"""Choosing the embedder at onboarding, reading it back, and keeping it.

The choice is made once: finishing onboarding locks it, the index reports it,
and nothing it depends on can be deleted while it is active.
"""

import pytest
from httpx import AsyncClient

from modules.embedding.bundled import BGE
from modules.llm.catalog.local.engines.onnxruntime.spec import spec_for
from modules.llm.catalog.local.manifest import load_local_manifest
from tests.integration.llm.installs import install_to_end

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

GRANITE = "granite-embedding-97m-multilingual-r2"
CHAT = {"provider": "llamacpp", "name": "Qwen3-1.7B-Q4_K_M"}


async def _install(client: AsyncClient, model_id: str) -> None:
    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    (row,) = [r for r in rows if r["id"] == model_id]
    job = await install_to_end(
        client, catalog_id=row["builds"][0]["catalog_id"], select=False
    )
    assert job["event"]["type"] == "complete", job


def _granite_spec() -> dict:
    (model,) = [m for m in load_local_manifest().models if m.id == GRANITE]
    return spec_for(model).model_dump(mode="json")


async def test_onboarding_locks_the_embedder_it_was_given(
    unlocked_client: AsyncClient, llamacpp_server: str, fake_hub
) -> None:
    """Downloaded during the step, fixed when the user finishes."""
    client = unlocked_client
    await client.put("/llm/selection/text_gen", json=CHAT)
    await _install(client, GRANITE)

    finished = await client.post("/llm/onboarding", json={"embedding_model": GRANITE})

    assert finished.status_code == 200, finished.text
    index = (await client.get("/embedding/index")).json()
    assert index["building"] is None
    assert index["active"]["spec"] == _granite_spec()
    assert index["active"]["name"] == "Granite Embedding 97M (Multilingual)"


async def test_an_embedder_not_yet_downloaded_cannot_be_locked(
    unlocked_client: AsyncClient, llamacpp_server: str
) -> None:
    """Locked without its files, nothing could ever be embedded."""
    client = unlocked_client
    await client.put("/llm/selection/text_gen", json=CHAT)

    refused = await client.post("/llm/onboarding", json={"embedding_model": GRANITE})

    assert refused.status_code == 409
    assert (await client.get("/embedding/index")).json()["active"] is None
    assert (await client.get("/llm/onboarding")).json() == {"completed": False}


async def test_the_index_is_empty_until_onboarding_chooses(
    unlocked_client: AsyncClient,
) -> None:
    """Settings reads this; before onboarding there is nothing to show."""
    index = await unlocked_client.get("/embedding/index")

    assert index.status_code == 200
    assert index.json() == {"active": None, "building": None}


async def test_the_active_embedder_cannot_be_deleted(
    unlocked_client: AsyncClient, llamacpp_server: str, fake_hub
) -> None:
    """Every vector in the library was made by it."""
    client = unlocked_client
    await client.put("/llm/selection/text_gen", json=CHAT)
    await _install(client, GRANITE)
    await client.post("/llm/onboarding", json={"embedding_model": GRANITE})

    refused = await client.delete(f"/llm/models/{GRANITE}")

    assert refused.status_code == 409
    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    (row,) = [r for r in rows if r["id"] == GRANITE]
    assert row["builds"][0]["installed_as"] == GRANITE


async def test_an_embedder_downloaded_but_not_chosen_can_be_deleted(
    client: AsyncClient, fake_hub
) -> None:
    """bge was locked; the download is spare."""
    await _install(client, GRANITE)

    deleted = await client.delete(f"/llm/models/{GRANITE}")

    assert deleted.status_code == 200, deleted.text
    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    (row,) = [r for r in rows if r["id"] == GRANITE]
    assert row["builds"][0]["installed_as"] is None


async def test_the_bundled_embedder_cannot_be_deleted(
    client: AsyncClient, data_dir
) -> None:
    """It is the way back once changing the model exists."""
    pack = data_dir / "models" / BGE.id
    pack.mkdir(parents=True)
    for pinned in (BGE.weights, BGE.tokenizer):
        (pack / pinned.path).write_bytes(b"onnx")

    refused = await client.delete(f"/llm/models/{BGE.id}")

    assert refused.status_code == 409
