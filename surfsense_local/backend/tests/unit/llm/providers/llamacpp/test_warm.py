"""Bringing a model into memory before someone waits on it.

A cold load is tens of seconds, and the router evicts on an idle timer, so the
question is never whether a load happens but whether it happens while the user
is watching.
"""

import pytest

from modules.llm.providers.llamacpp.warm import warm_model
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit

MODEL = "Qwen3-1.7B-Q4_K_M"


def frame(status: str, value: float | None = None, model: str = MODEL) -> dict:
    """One status frame, with progress only where the router has a figure."""
    data: dict = {"status": status}
    if value is not None:
        data["progress"] = {
            "stages": ["text_model"],
            "current": "text_model",
            "value": value,
        }
    return {"model": model, "event": "status_change", "data": data}


async def collect(router: FakeRouter, model: str = MODEL) -> list:
    """Every step the warm reports, start to finish."""
    return [
        progress
        async for progress in warm_model(
            "http://router", model, transport=router.transport()
        )
    ]


async def test_warming_asks_the_router_to_load_the_model() -> None:
    """The point of the call. Without it the load happens on the request that
    needed it, which is the one the user is waiting on."""
    router = FakeRouter(models=[MODEL])
    router.sse_events = [frame("loaded")]

    await collect(router)

    assert router.load_calls == [MODEL]


async def test_progress_is_reported_while_the_load_runs() -> None:
    """What turns a silent wait into one with an end in sight."""
    router = FakeRouter(models=[MODEL])
    router.sse_events = [frame("loading", 0.0), frame("loading", 0.6), frame("loaded")]

    assert [p.value for p in await collect(router)] == [0.0, 0.6, None]


async def test_another_model_loading_is_not_reported_as_this_one() -> None:
    """One stream covers every model, and `--models-max 1` means a load can be
    evicting whatever was resident. Reporting that as this model's progress
    would move a bar the user is reading."""
    router = FakeRouter(models=[MODEL])
    router.sse_events = [frame("loading", 0.5, model="something-else"), frame("loaded")]

    assert [p.model_id for p in await collect(router)] == [MODEL]


async def test_a_model_already_resident_is_the_state_the_caller_wanted() -> None:
    """The router answers 400 `model is already running`, which is success for
    a caller that means "be loaded", not a failure to report."""
    router = FakeRouter(models=[MODEL])
    router.already_running = {MODEL}
    router.sse_events = [frame("loaded")]

    assert [p.status for p in await collect(router)] == ["loaded"]


async def test_the_watch_stops_once_the_model_is_loaded() -> None:
    """The stream outlives the load and carries every other model's events, so
    a caller that did not stop would never finish its install."""
    router = FakeRouter(models=[MODEL])
    router.sse_events = [frame("loaded"), frame("loading", 0.1)]

    assert len(await collect(router)) == 1


async def test_a_load_that_gives_up_ends_the_watch_too() -> None:
    """`unloaded` is how the router reports a worker that died. Waiting past it
    would hang the install on a model that is never coming."""
    router = FakeRouter(models=[MODEL])
    router.sse_events = [frame("loading", 0.2), frame("unloaded")]

    assert [p.status for p in await collect(router)] == ["loading", "unloaded"]
