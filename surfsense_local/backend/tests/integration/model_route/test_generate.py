"""The model route: text generation for processes other than the API."""

import asyncio
import json
import threading

import pytest
from httpx import AsyncClient

from modules.llm.activity import model_activity, model_key
from modules.llm.admission.pool import Priority
from tests.integration.model_route.conftest import (
    ANSWER,
    LOCAL_MODEL,
    OTHER_LOCAL_MODEL,
    App,
    Runtime,
)

pytestmark = pytest.mark.integration

ROUTE = "/internal/models/text/generate"


def local_request(**extra: object) -> dict:
    """A Studio request for the local model, as the worker sends one."""
    return {
        "model": {"provider": "llamacpp", "name": LOCAL_MODEL, "connection_id": None},
        "messages": [{"role": "user", "content": "Summarise Saturn."}],
        "max_tokens": 200,
        "reasoning": False,
        "priority": "background",
        **extra,
    }


async def frames(client: AsyncClient, body: dict) -> tuple[int, list[dict]]:
    """The route's status and its frames, up to `[DONE]`."""
    reply = await client.post(ROUTE, json=body)
    if reply.status_code != 200:
        return reply.status_code, []
    events = []
    for line in reply.text.splitlines():
        if line.startswith("data: {"):
            events.append(json.loads(line[len("data: ") :]))
    assert "data: [DONE]" in reply.text
    return 200, events


async def test_studio_on_the_local_runtime_waits_behind_a_chat_and_says_where_it_stands(
    api: App, runtime: Runtime
) -> None:
    """Studio is background work: it waits behind a chat and hears its place."""
    held = api.app.state.local_admission.admitted(
        LOCAL_MODEL, [], 10, Priority.INTERACTIVE
    )
    await held.__aenter__()
    asking = asyncio.create_task(frames(api.client, local_request()))
    for _ in range(20):
        await asyncio.sleep(0.01)
    seen_while_held = list(runtime.requests)
    await held.__aexit__(None, None, None)
    status, events = await asking

    assert seen_while_held == []
    assert status == 200
    assert events[0] == {"type": "queued", "position": 1}
    assert "".join(e["text"] for e in events if e["type"] == "text") == "".join(ANSWER)


async def test_two_requests_arriving_together_share_one_count_of_the_slots(
    api: App, runtime: Runtime
) -> None:
    """The first requests for a model each read its slots, and must still be
    counted together: one slot means one generation, however they arrived."""
    runtime.stall = threading.Event()

    asking = [asyncio.create_task(frames(api.client, local_request())) for _ in "ab"]
    for _ in range(50):
        await asyncio.sleep(0.01)
    reached_while_stalled = len(runtime.requests)
    runtime.stall.set()
    replies = await asyncio.gather(*asking)

    assert reached_while_stalled == 1
    assert [status for status, _ in replies] == [200, 200]
    assert len(runtime.requests) == 2


async def test_a_worker_that_hangs_up_before_the_reply_starts_leaves_the_model_free(
    api: App, runtime: Runtime
) -> None:
    """A model marked in use cannot be deleted, so the mark must go whenever
    the worker leaves, even before the first frame was sent."""
    body = json.dumps(local_request()).encode()
    received = iter([{"type": "http.request", "body": body, "more_body": False}])

    async def receive() -> dict:
        return next(received, {"type": "http.disconnect"})

    async def send(_message: dict) -> None:
        await asyncio.sleep(0)

    await api.app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": ROUTE,
            "raw_path": ROUTE.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 80),
        },
        receive,
        send,
    )

    async with model_activity.deleting(model_key("llamacpp", LOCAL_MODEL)):
        pass


async def test_a_remote_model_is_not_admitted_and_answers_at_once(
    api: App, runtime: Runtime, remote_connection: int
) -> None:
    """A remote host has its own servers: a busy local runtime holds nothing up."""
    held = api.app.state.local_admission.admitted(
        LOCAL_MODEL, [], 10, Priority.INTERACTIVE
    )
    await held.__aenter__()
    try:
        status, events = await frames(
            api.client,
            local_request(
                model={
                    "provider": "openai_compatible",
                    "name": "remote-model",
                    "connection_id": remote_connection,
                }
            ),
        )
    finally:
        await held.__aexit__(None, None, None)

    assert status == 200
    assert not any(e["type"] == "queued" for e in events)
    assert "".join(e["text"] for e in events if e["type"] == "text") == "".join(ANSWER)


async def test_the_named_model_answers_even_when_another_is_selected(
    api: App, runtime: Runtime
) -> None:
    """A Studio job keeps the model it started with, whatever is selected now."""
    status, _events = await frames(
        api.client,
        local_request(
            model={
                "provider": "llamacpp",
                "name": OTHER_LOCAL_MODEL,
                "connection_id": None,
            }
        ),
    )

    assert status == 200
    assert runtime.requests[0]["model"] == OTHER_LOCAL_MODEL


async def test_a_model_deleted_since_is_a_409(api: App, runtime: Runtime) -> None:
    """The API resolves the model, so a deleted one never reaches the runtime."""
    status, _events = await frames(
        api.client,
        local_request(
            model={"provider": "llamacpp", "name": "Gone-Q4_K_M", "connection_id": None}
        ),
    )

    assert status == 409
    assert runtime.requests == []


async def test_a_provider_refusal_comes_back_as_its_status(
    api: App, runtime: Runtime
) -> None:
    """The provider's status crosses the route, for the worker to raise as before."""
    runtime.status = 429

    status, events = await frames(api.client, local_request())

    assert status == 200
    assert events[-1]["type"] == "error"
    assert events[-1]["error"] == "http_status"
    assert events[-1]["status"] == 429
