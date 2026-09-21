"""Talking to llama-server in router mode."""

import httpx
import pytest

from modules.llm.providers.llamacpp import RouterClient
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


def client_for(fake: FakeRouter) -> RouterClient:
    """A client wired to a fake router rather than a live sidecar."""
    return RouterClient(
        "http://127.0.0.1:1234",
        transport=fake.transport(),
    )


@pytest.mark.asyncio
async def test_a_healthy_router_answers() -> None:
    """The sidecar is up. Everything else is gated on this."""
    assert await client_for(FakeRouter()).health() is True


@pytest.mark.asyncio
async def test_router_mode_is_confirmed_rather_than_assumed() -> None:
    """`/props` reporting role=router is the reliable check that the sidecar came
    up in router mode rather than single-model mode, which answers /health too."""
    assert await client_for(FakeRouter()).is_router() is True


@pytest.mark.asyncio
async def test_an_empty_models_directory_is_a_working_router_not_a_failure() -> None:
    """Verified against the real binary: the whole lifecycle is testable before
    any model exists, which is what makes the sidecar shippable on its own."""
    assert await client_for(FakeRouter([])).models() == []


@pytest.mark.asyncio
async def test_discovered_models_report_whether_they_are_resident() -> None:
    """Residency decides whether the next turn pays a reload."""
    fake = FakeRouter(["Qwen3-8B-Q4_K_M"])
    fake.loaded.add("Qwen3-8B-Q4_K_M")

    models = await client_for(fake).models()

    assert models[0].id == "Qwen3-8B-Q4_K_M"
    assert models[0].loaded is True


@pytest.mark.asyncio
async def test_loading_and_unloading_move_a_model_in_and_out_of_memory() -> None:
    """The two calls the chat path and a cancelled download rely on."""
    fake = FakeRouter(["m"])
    client = client_for(fake)

    await client.load("m")
    assert fake.loaded == {"m"}

    await client.unload("m")
    assert fake.loaded == set()


@pytest.mark.asyncio
async def test_the_routers_own_delete_refuses_models_we_installed() -> None:
    """Recorded because the contract table said this would work and it does not.

    `DELETE /models` only removes what the router downloaded into its own cache.
    Anything staged into `--models-dir`, which is everything SurfSense installs,
    comes back `not removable (not from cache)`. Deletion is ours to do.
    """
    fake = FakeRouter(["m"])

    with pytest.raises(httpx.HTTPStatusError):
        await client_for(fake).delete("m")


@pytest.mark.asyncio
async def test_an_unreachable_router_is_unhealthy_rather_than_an_exception() -> None:
    """The catalog stays visible when the runtime is down; installs disable."""

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    client = RouterClient("http://127.0.0.1:1", transport=httpx.MockTransport(refuse))

    assert await client.health() is False


@pytest.mark.asyncio
async def test_tokenize_counts_against_the_models_own_tokenizer() -> None:
    """The exact count the router's tokenizer gives, not a heuristic."""
    fake = FakeRouter(["qwen3"])
    fake.tokens_per_word = 3

    count = await client_for(fake).tokenize("qwen3", "three little words")

    assert count == 9


@pytest.mark.asyncio
async def test_tokenize_raises_on_a_router_that_does_not_answer() -> None:
    """An older build, or a transient failure: the caller decides the fallback,
    this does not silently return zero."""

    def _404(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = RouterClient("http://127.0.0.1:1234", transport=httpx.MockTransport(_404))

    with pytest.raises(httpx.HTTPError):
        await client.tokenize("qwen3", "hi")
