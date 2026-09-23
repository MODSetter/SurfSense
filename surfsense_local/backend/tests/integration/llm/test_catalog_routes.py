"""The model screen's routes.

These replace `GET /llm/system`, `GET /llm/catalog` and `POST /llm/install` at
the same paths, so this file is also the check that the reshape landed.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from modules.llm.catalog import CatalogService, load_curated_models
from modules.llm.catalog.dependencies import get_catalog_service
from shared.db import create_session_factory

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_the_catalog_renders_with_no_network_and_no_scan(
    client: AsyncClient,
) -> None:
    """A clean machine sees a hardware line and badged rows on first paint."""
    reply = await client.get("/llm/catalog")

    assert reply.status_code == 200
    body = reply.json()
    assert body["curated"]
    assert all(row["badge"]["verdict"] for row in body["curated"])


async def test_curated_rows_preserve_each_models_shape(
    engine: Engine, tmp_path: Path
) -> None:
    """Each card receives its own context window and architecture from the manifest."""
    manifest = load_curated_models()
    manifest.models = manifest.models[:2]
    first, second = manifest.models
    first.model_id = "example/short-window"
    first.shape = first.shape.model_copy(
        update={"architecture": "llama", "context_length": 8192}
    )
    second.model_id = "example/long-window"
    second.shape = second.shape.model_copy(
        update={"architecture": "qwen3", "context_length": 32768}
    )
    service = CatalogService(
        manifest,
        tmp_path / "models",
        tmp_path / "lib",
        probe=lambda _: [],
        os_gpu=lambda: False,
    )
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    app.dependency_overrides[get_catalog_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        reply = await client.get("/llm/catalog")

    assert reply.status_code == 200
    assert {
        row["model_id"]: (row["context_length"], row.get("architecture"))
        for row in reply.json()["curated"]
    } == {
        "example/short-window": (8192, "llama"),
        "example/long-window": (32768, "qwen3"),
    }


async def test_no_row_carries_a_rank_on_the_wire(client: AsyncClient) -> None:
    """Asserted on the serialized response, so it cannot be reintroduced by an
    accidental `from_attributes` widening."""
    body = (await client.get("/llm/catalog")).json()

    for row in body["curated"]:
        assert "rank" not in row
        assert "score" not in row


async def test_the_response_carries_no_scanned_flag(client: AsyncClient) -> None:
    """There is no scan. The flag is what the frontend hung a button on."""
    body = (await client.get("/llm/catalog")).json()

    assert "scanned" not in body


async def test_the_offload_fraction_survives_to_the_renderer(
    client: AsyncClient,
) -> None:
    """The graded reason line is selected from it, and the renderer must not
    recompute what the estimator already knows."""
    body = (await client.get("/llm/catalog")).json()

    assert all("offload_fraction" in row["fit"] for row in body["curated"])


async def test_the_system_route_describes_one_device_never_a_sum(
    client: AsyncClient,
) -> None:
    """Summing backends reports 12 GB on a 6 GB card, wrong in the dangerous
    direction: it tells a user a model fits when it cannot."""
    body = (await client.get("/llm/system")).json()

    budget = body["budget"]
    assert budget["usable_vram_bytes"] <= budget["device_free_bytes"]
    for device in body["devices"]:
        assert budget["device_total_bytes"] <= max(
            device["total_bytes"] for device in body["devices"]
        )


async def test_search_is_refused_until_its_destination_is_allowed(
    client: AsyncClient,
) -> None:
    """Typing into a search box sends that text to huggingface.co, which is a
    consent of its own and separate from allowing a download."""
    reply = await client.get("/llm/search", params={"q": "qwen"})

    assert reply.status_code == 403


async def test_installing_an_unknown_id_says_the_catalog_is_stale(
    client: AsyncClient,
) -> None:
    """One staleness failure, not two: a searched build's ticket expires on the
    same clock as the row it was minted for."""
    reply = await client.post("/llm/install", json={"catalog_id": "never-minted"})

    assert reply.status_code == 422
    assert "stale" in reply.json()["detail"]


async def test_installing_is_refused_until_its_destination_is_allowed(
    client: AsyncClient,
) -> None:
    """Downloading a model reaches huggingface.co, and that is a consent the
    user gives explicitly. Separate from search: this is a repo they named.
    """
    body = (await client.get("/llm/catalog")).json()
    catalog_id = body["curated"][0]["catalog_id"]

    reply = await client.post("/llm/install", json={"catalog_id": catalog_id})

    assert reply.status_code == 403


async def test_a_curated_row_can_be_installed_by_its_opaque_id(
    client: AsyncClient,
) -> None:
    """The renderer sends only that id: no repo, file, URL or path. A valid id
    gets past resolution and fails on egress, not on being unrecognised."""
    body = (await client.get("/llm/catalog")).json()
    catalog_id = body["curated"][0]["catalog_id"]

    reply = await client.post("/llm/install", json={"catalog_id": catalog_id})

    assert reply.status_code != 422


async def test_the_system_route_says_whether_the_runtime_sees_the_hardware(
    client: AsyncClient,
) -> None:
    """An empty device list means nothing on its own: a machine with no card and
    a machine whose card the runtime cannot reach both report one."""
    body = (await client.get("/llm/system")).json()

    assert body["gpu_status"] in {"present", "absent", "broken_install", "unknown"}


async def test_the_catalog_carries_the_same_diagnosis(client: AsyncClient) -> None:
    """The screen that renders the badges is the one that has to explain them."""
    body = (await client.get("/llm/catalog")).json()

    assert body["gpu_status"] in {"present", "absent", "broken_install", "unknown"}


async def test_the_budget_never_reports_a_gpu_diagnosis(client: AsyncClient) -> None:
    """The budget is memory. Phase 8.3 asks for a distinct state, not a flag
    folded into the numbers, so a reader of one cannot mistake it for the other.
    """
    body = (await client.get("/llm/system")).json()

    assert "gpu_status" not in body["budget"]
