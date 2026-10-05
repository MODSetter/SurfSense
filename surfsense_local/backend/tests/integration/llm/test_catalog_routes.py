"""The local catalog's routes: offline rows, gated search, opaque installs."""

import pytest
from httpx import AsyncClient

from modules.llm.catalog.local import service as service_module
from modules.llm.fit import HardwareBudget

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_the_catalog_renders_with_no_network_and_no_scan(
    client: AsyncClient,
) -> None:
    """The catalog renders with no network and no scan."""
    reply = await client.get("/llm/catalog/local")

    assert reply.status_code == 200
    body = reply.json()
    curated = [row for row in body["rows"] if row["origin"] == "curated" and row["engine"] == "llamacpp"]
    assert curated
    # A badge names a verdict exactly when it warns.
    for row in curated:
        for build in row["builds"]:
            badge = build["badge"]
            assert badge["level"] in {"none", "notice", "refuse"}
            assert bool(badge["verdict"]) == (badge["level"] != "none")
            # A badge that says anything names it, for the interface to word.
            assert (badge["code"] is None) == (badge["reason"] == "")
    assert body["projector_notices"] == []
    assert "scanned" not in body


async def test_a_badge_carries_its_tier_and_unified_memory(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the interface needs to word a refusal as "This Mac" in its language."""
    mib = 1024**2
    apple = HardwareBudget(5461 * mib, 5461 * mib, 1024 * mib, 6144 * mib, True, True)
    monkeypatch.setattr(service_module, "build_budget", lambda *_, **__: apple)

    body = (await client.get("/llm/catalog/local")).json()

    badges = [
        build["badge"]
        for row in body["rows"]
        if row["engine"] == "llamacpp"
        for build in row["builds"]
    ]
    refused = [badge for badge in badges if badge["level"] == "refuse"]
    assert refused
    assert all(badge["code"] == "too_big" and badge["uma"] for badge in refused)


async def test_every_local_row_has_one_shape(client: AsyncClient) -> None:
    """Every local row has one shape."""
    body = (await client.get("/llm/catalog/local")).json()

    for row in body["rows"]:
        assert row["source"] == "local"
        assert {"types", "selectable_for", "support", "builds", "runnable"} <= set(row)
        # A reason and its code come and go together with `runnable`.
        assert {"not_runnable_reason", "not_runnable_code"} <= set(row)
        if row["runnable"]:
            assert row["not_runnable_reason"] is None
            assert row["not_runnable_code"] is None
        assert "reads_images" in row["support"]
        for build in row["builds"]:
            assert {
                "footprint_bytes",
                "files",
                "reads_images",
                "projector_checked",
            } <= set(build)


async def test_no_row_carries_a_rank_on_the_wire(client: AsyncClient) -> None:
    """No row carries a rank on the wire."""
    body = (await client.get("/llm/catalog/local")).json()

    for row in body["rows"]:
        for field in ("rank", "score", "position"):
            assert field not in row


async def test_each_curated_model_names_its_default_and_at_most_one_recommended_build(
    client: AsyncClient,
) -> None:
    """Each curated model names its default and at most one recommended build."""
    body = (await client.get("/llm/catalog/local")).json()

    for row in body["rows"]:
        if row["origin"] == "curated" and row["engine"] == "llamacpp":
            assert row["default_quantization"] == "UD-Q4_K_XL"
            assert sum(b["recommended"] for b in row["builds"]) <= 1


async def test_the_offload_fraction_survives_to_the_renderer(
    client: AsyncClient,
) -> None:
    """The offload fraction survives to the renderer."""
    body = (await client.get("/llm/catalog/local")).json()

    assert all(
        "offload_fraction" in b["fit"]
        for row in body["rows"]
        if row["engine"] == "llamacpp"
        for b in row["builds"]
    )


async def test_the_system_route_describes_one_device_never_a_sum(
    client: AsyncClient,
) -> None:
    """The system route describes one device never a sum."""
    body = (await client.get("/llm/system")).json()

    budget = body["budget"]
    assert budget["usable_vram_bytes"] <= budget["device_free_bytes"]
    assert body["gpu_status"] in {"present", "absent", "broken_install", "unknown"}
    assert "gpu_status" not in budget


async def test_search_is_refused_until_its_destination_is_allowed(
    client: AsyncClient,
) -> None:
    """Search is refused until its destination is allowed."""
    assert (
        await client.get("/llm/catalog/local/search", params={"q": "qwen"})
    ).status_code == 403
    assert (
        await client.get("/llm/catalog/local/search/unsloth/Qwen3-8B-GGUF")
    ).status_code == 403


async def test_installing_an_unknown_id_says_the_catalog_is_stale(
    client: AsyncClient,
) -> None:
    """Installing an unknown id says the catalog is stale."""
    reply = await client.post("/llm/installs", json={"catalog_id": "never-minted"})

    assert reply.status_code == 422
    assert "stale" in reply.json()["detail"]


async def test_a_curated_build_is_installed_by_its_opaque_id(
    client: AsyncClient,
) -> None:
    """A valid id gets past resolution and fails on egress, not on being unknown."""
    body = (await client.get("/llm/catalog/local")).json()
    catalog_id = body["rows"][0]["builds"][0]["catalog_id"]

    reply = await client.post("/llm/installs", json={"catalog_id": catalog_id})

    assert reply.status_code == 403


async def test_every_curated_row_says_which_build_it_leads_with_and_why(
    client: AsyncClient,
) -> None:
    """The screen computes nothing: the server names the build Download fetches."""
    body = (await client.get("/llm/catalog/local")).json()

    for row in body["rows"]:
        if row["origin"] == "curated" and row["engine"] == "llamacpp":
            lead = row["lead"]
            assert lead["why"] in {
                "in_use",
                "installed",
                "recommended",
                "fits_slower",
                "nothing_fits",
            }
            assert lead["quantization"] in {b["quantization"] for b in row["builds"]}


async def test_an_install_that_is_not_running_cannot_be_cancelled(
    client: AsyncClient,
) -> None:
    """Cancel names a job; one unknown or over is a 404, not a silent no-op."""
    assert (await client.delete("/llm/installs/never-started")).status_code == 404
    assert (await client.get("/llm/installs/never-started")).status_code == 404


async def test_the_install_list_starts_empty(client: AsyncClient) -> None:
    """A fresh app has no jobs, so no screen shows a download."""
    assert (await client.get("/llm/installs")).json() == {"jobs": []}
