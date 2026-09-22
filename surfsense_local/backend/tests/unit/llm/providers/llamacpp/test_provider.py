"""The adapter the rest of the app sees.

It satisfies the same protocol the previous runtime did, so nothing above it learns that
the runtime changed.
"""

import pytest

from modules.llm.providers.llamacpp import LlamaCppProvider
from modules.llm.providers.types import Message
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


def provider_for(fake: FakeRouter) -> LlamaCppProvider:
    """A provider wired to a fake router rather than a live sidecar."""
    return LlamaCppProvider("http://127.0.0.1:1234", transport=fake.transport())


def test_it_is_the_registry_entry_the_selection_column_will_hold() -> None:
    """Revision 0012 rewrites `selected_models.provider` to exactly this."""
    assert LlamaCppProvider("http://x").name == "llamacpp"


def test_it_answers_and_keeps_inventory_without_pulling_its_own_weights() -> None:
    """This runtime deliberately has no `pull()`.

    The previous runtime pulled its own weights, so a name was enough. Here SurfSense fetches
    the GGUF in process, which is the only place `egress.require()` actually
    holds, and it also buys resume, checksums and the header as the file lands.
    Downloads are a catalog concern, not a runtime one, so a `pull` here would
    advertise a capability that belongs somewhere else.
    """
    provider = LlamaCppProvider("http://x")

    assert not hasattr(provider, "pull")
    assert callable(provider.health)
    assert callable(provider.models)
    assert callable(provider.chat)
    assert callable(provider.delete)


@pytest.mark.asyncio
async def test_installed_models_come_from_the_router() -> None:
    """The router auto-discovers the models directory, so disk is the source of truth."""
    models = await provider_for(FakeRouter(["Qwen3-8B-Q4_K_M"])).models()

    assert [m.name for m in models] == ["Qwen3-8B-Q4_K_M"]
    assert models[0].installed


@pytest.mark.asyncio
async def test_a_cold_model_answers_without_us_loading_it() -> None:
    """The router discovers models as `unloaded`, and loads one on the request
    that needs it: `--models-autoload` is on by default and the proxy calls
    `ensure_model_ready` before forwarding. So the first turn works against a
    model nobody has asked for yet, and asking as well only created a race."""
    fake = FakeRouter(["m"])

    chunks = [c async for c in provider_for(fake).chat("m", [Message("user", "hi")])]

    assert "".join(chunks) == "Hello"
    assert fake.load_calls == []


@pytest.mark.asyncio
async def test_an_already_resident_model_is_not_reloaded() -> None:
    """Reloading would evict and re-read gigabytes between two turns."""
    fake = FakeRouter(["m"])
    fake.loaded.add("m")
    calls_before = len(fake.chat_bodies)

    async for _ in provider_for(fake).chat("m", [Message("user", "hi")]):
        pass

    assert len(fake.chat_bodies) == calls_before + 1


@pytest.mark.asyncio
async def test_the_request_names_the_model_and_asks_for_a_stream() -> None:
    """Chat is composed from the OpenAI provider, so the body must be its shape."""
    fake = FakeRouter(["m"])

    async for _ in provider_for(fake).chat("m", [Message("user", "hi")]):
        pass

    body = fake.chat_bodies[-1]
    assert body["model"] == "m"
    assert body["stream"] is True


@pytest.mark.asyncio
async def test_a_template_without_a_system_role_still_gets_the_grounding() -> None:
    """End to end through the adapter: the fold happens at this seam, so nothing
    above it has to know which template the chosen model uses."""
    fake = FakeRouter(["m"])
    fake.loaded.add("m")
    fake.template_caps = {"supports_system_role": False}

    async for _ in provider_for(fake).chat(
        "m",
        [Message("system", "Cite with [n]."), Message("user", "hi")],
    ):
        pass

    sent = fake.chat_bodies[-1]["messages"]
    assert [m["role"] for m in sent] == ["user"]
    assert "Cite with [n]." in sent[0]["content"]


@pytest.mark.asyncio
async def test_a_normal_template_is_left_alone() -> None:
    """The common case: nothing is folded and nothing moves."""
    fake = FakeRouter(["m"])
    fake.loaded.add("m")

    async for _ in provider_for(fake).chat(
        "m",
        [Message("system", "Cite with [n]."), Message("user", "hi")],
    ):
        pass

    assert [m["role"] for m in fake.chat_bodies[-1]["messages"]] == ["system", "user"]


@pytest.mark.asyncio
async def test_deleting_removes_the_weights_from_disk(tmp_path) -> None:
    """The router cannot do this for us.

    `DELETE /models` only removes models the router downloaded into its own
    cache; anything staged into `--models-dir` comes back `not removable (not
    from cache)` with a 500 and the file untouched. Everything SurfSense
    installs lands there, so deletion is ours, symmetrically with install.
    """
    models = tmp_path / "models"
    models.mkdir()
    (models / "m.gguf").write_bytes(b"GGUF weights")
    fake = FakeRouter(["m"])
    provider = LlamaCppProvider(
        "http://127.0.0.1:1234", models, transport=fake.transport()
    )

    await provider.delete("m")

    assert not (models / "m.gguf").exists()
    assert fake.deleted == []


@pytest.mark.asyncio
async def test_deleting_something_absent_says_so(tmp_path) -> None:
    """A stale row, or a file removed outside the app."""
    models = tmp_path / "models"
    models.mkdir()
    provider = LlamaCppProvider("http://127.0.0.1:1234", models)

    with pytest.raises(FileNotFoundError):
        await provider.delete("never-installed")


@pytest.mark.asyncio
async def test_capabilities_are_cached_for_a_resident_model() -> None:
    """`/props` describes a resident model, and nothing about it changes
    between turns: asking twice should cost one round trip, not two.

    Measured live: `context_tokens()` and `chat()`'s own template shaping each
    read `/props` independently on every single message, which is two calls
    where one answer would do, and which showed up as real, avoidable latency
    on an already slow load.
    """
    fake = FakeRouter(["qwen3"])
    fake.loaded.add("qwen3")
    provider = provider_for(fake)

    await provider.capabilities("qwen3")
    await provider.capabilities("qwen3")

    assert fake.props_calls == 1


@pytest.mark.asyncio
async def test_the_capability_cache_cannot_outlive_its_adapter() -> None:
    """Why nothing invalidates it any more.

    The answer `/props` gives is a property of the file and the preset, and a
    preset rewrite restarts the sidecar. But `get_provider()` builds a fresh
    adapter per call, so a cache entry cannot survive even one resolution, let
    alone a restart. Within one adapter the answer cannot change, and across
    adapters there is no cache to be stale.
    """
    fake = FakeRouter(["qwen3"])
    provider = provider_for(fake)

    async for _ in provider.chat("qwen3", [Message("user", "hi")]):
        pass
    async for _ in provider.chat("qwen3", [Message("user", "hi")]):
        pass
    assert fake.props_calls == 1, "a resident model's template does not change"

    async for _ in provider_for(fake).chat("qwen3", [Message("user", "hi")]):
        pass
    assert fake.props_calls == 2, "a new adapter carries nothing over"


async def test_a_turn_never_asks_the_router_to_load(anyio_backend) -> None:
    """The router loads on demand and we stop having an opinion about it.

    `--models-autoload` is enabled by default and the proxy calls
    `ensure_model_ready` before forwarding, so a chat request loads a cold model
    on its own. Asking as well was a check-then-act across a socket: read
    `/models`, see `loaded: false`, post `/models/load`, and lose the race to
    the request that was already loading it. The router answers 400 `model is
    already running`, which took out title generation on every new thread.
    """
    fake = FakeRouter(["Qwen3-1.7B-Q4_K_M"])
    provider = provider_for(fake)

    async for _ in provider.chat("Qwen3-1.7B-Q4_K_M", [Message("user", "hi")]):
        pass

    assert fake.load_calls == []


async def test_a_load_that_lost_the_race_is_not_an_error(anyio_backend) -> None:
    """For the callers that do mean "load now", such as a warm up after an
    install. `model is already running` is the state they wanted, and anything
    crossing this socket can be beaten to it."""
    fake = FakeRouter(["Qwen3-1.7B-Q4_K_M"])
    fake.already_running.add("Qwen3-1.7B-Q4_K_M")
    provider = provider_for(fake)

    await provider._router.load("Qwen3-1.7B-Q4_K_M")

    assert fake.load_calls == ["Qwen3-1.7B-Q4_K_M"]
