"""The router's own account of what it is loading.

Event shapes are what `GET /models/sse` streamed at b11050, captured from a
real load rather than written from the docs.
"""

import pytest

from modules.llm.providers.llamacpp.model_events import LoadProgress, watch_models
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


def loading(value: float, stage: str = "text_model") -> dict:
    """One frame of a load in progress, as the router sends it."""
    return {
        "model": "Qwen3-1.7B-Q4_K_M",
        "event": "status_change",
        "data": {
            "status": "loading",
            "progress": {"stages": [stage], "current": stage, "value": value},
        },
    }


async def collect(router: FakeRouter) -> list[LoadProgress]:
    """Everything the watch reports, for a stream that ends on its own."""
    return [
        event
        async for event in watch_models("http://router", transport=router.transport())
    ]


async def test_a_load_reports_how_far_along_it_is() -> None:
    """The whole point: a wait the user can see the end of."""
    router = FakeRouter()
    router.sse_events = [loading(0.0), loading(0.4), loading(1.0)]

    assert [event.value for event in await collect(router)] == [0.0, 0.4, 1.0]


async def test_progress_carries_the_model_it_belongs_to() -> None:
    """One stream covers every model, and `--models-max 1` means a load can be
    evicting the model the caller actually asked about."""
    router = FakeRouter()
    router.sse_events = [loading(0.5)]

    assert (await collect(router))[0].model_id == "Qwen3-1.7B-Q4_K_M"


async def test_the_stage_is_reported_because_a_load_has_more_than_one() -> None:
    """A vision model loads its projector after its weights, so a bar that only
    knew the first would sit at 100% through the second."""
    router = FakeRouter()
    router.sse_events = [loading(1.0, "text_model"), loading(0.2, "mmproj_model")]

    assert [event.stage for event in await collect(router)] == [
        "text_model",
        "mmproj_model",
    ]


async def test_a_status_without_progress_still_reports_the_status() -> None:
    """The router announces `loading` before it has a figure, and announces
    `ready` with none at all. Dropping those would lose the two transitions a
    caller most needs."""
    router = FakeRouter()
    router.sse_events = [
        {"model": "m", "event": "model_status", "data": {"status": "loading"}},
        {"model": "m", "event": "status_change", "data": {"status": "ready"}},
    ]

    events = await collect(router)

    assert [event.status for event in events] == ["loading", "ready"]
    assert [event.value for event in events] == [None, None]


async def test_a_frame_that_is_not_json_is_skipped_rather_than_ending_the_watch() -> (
    None
):
    """SSE carries comments and keepalives, and this stream outlives them."""
    router = FakeRouter()
    router.sse_events = [loading(0.3)]

    events = [
        event
        async for event in watch_models("http://router", transport=router.transport())
    ]

    assert len(events) == 1
