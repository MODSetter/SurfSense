"""Embedding models in the one local catalog, offered by onnxruntime: listed and
downloaded like any model, and never a slot."""

import pytest
from httpx import AsyncClient

from modules.embedding.bundled import BGE
from modules.embedding.encoder import missing_files
from modules.llm.catalog.local.engines.onnxruntime.spec import spec_for
from modules.llm.catalog.local.manifest import load_local_manifest
from tests.integration.llm.installs import install_to_end

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

GRANITE = "granite-embedding-97m-multilingual-r2"


def embedding_rows(body: dict) -> dict[str, dict]:
    """The rows onnxruntime offered, by id."""
    return {r["id"]: r for r in body["rows"] if r["engine"] == "onnxruntime"}


@pytest.fixture
def bundled_bge(data_dir):
    """The models pack as the build script leaves it: bge's files, read-only."""
    pack = data_dir / "models" / BGE.id
    pack.mkdir(parents=True)
    for pinned in (BGE.weights, BGE.tokenizer):
        (pack / pinned.path).write_bytes(b"onnx")
    return pack


async def test_embedders_are_rows_that_fill_no_slot(client: AsyncClient) -> None:
    """Downloadable from the catalog, chosen only at onboarding."""
    rows = embedding_rows((await client.get("/llm/catalog/local")).json())

    assert {BGE.id, GRANITE} <= set(rows)
    granite = rows[GRANITE]
    assert granite["types"] == ["embedding"]
    assert granite["selectable_for"] == []
    assert granite["runnable"]
    # Onboarding says what each is for; the manifest is where a person wrote it.
    assert granite["description"] == "Search across more than 50 languages."


async def test_the_embedder_the_app_ships_reads_installed_and_bundled(
    client: AsyncClient, bundled_bge
) -> None:
    """In the installer, so on this computer from the first start."""
    rows = embedding_rows((await client.get("/llm/catalog/local")).json())

    (build,) = rows[BGE.id]["builds"]
    assert (build["installed_as"], build["bundled"]) == (BGE.id, True)


async def test_an_embedder_installs_where_the_encoder_reads_it(
    client: AsyncClient, fake_hub
) -> None:
    """Named by its catalog id: every ONNX repo calls its weights model.onnx."""
    rows = embedding_rows((await client.get("/llm/catalog/local")).json())
    (build,) = rows[GRANITE]["builds"]

    job = await install_to_end(client, catalog_id=build["catalog_id"], select=False)

    assert job["event"]["type"] == "complete", job
    (model,) = [m for m in load_local_manifest().models if m.id == GRANITE]
    assert missing_files(spec_for(model)) == []
    rows = embedding_rows((await client.get("/llm/catalog/local")).json())
    assert rows[GRANITE]["builds"][0]["installed_as"] == GRANITE
