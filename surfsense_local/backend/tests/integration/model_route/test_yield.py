"""Local image generation gives up the runtime through the API, not under a chat."""

import asyncio
import json
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from sqlalchemy import Engine

from api.main import create_app
from shared.db import create_session_factory
from tests.integration.model_route.conftest import LOCAL_MODEL, Runtime

pytestmark = pytest.mark.integration


@pytest.fixture
def live(engine: Engine) -> Iterator[str]:
    """The app on a real port, so a held stream can be read as it arrives."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    server.should_exit = True
    thread.join(timeout=5)


def _generate_body() -> dict:
    return {
        "model": {"provider": "llamacpp", "name": LOCAL_MODEL, "connection_id": None},
        "messages": [{"role": "user", "content": "Summarise Saturn."}],
        "max_tokens": 100,
    }


async def _generate(client: httpx.AsyncClient, seen: list[dict]) -> None:
    async with client.stream(
        "POST", "/internal/models/text/generate", json=_generate_body()
    ) as reply:
        async for line in reply.aiter_lines():
            if line.startswith("data: {"):
                seen.append(json.loads(line[len("data: ") :]))


async def test_an_image_job_waits_for_running_replies_then_holds_the_runtime(
    live: str, runtime: Runtime
) -> None:
    """Nothing running is cut off, and nothing new loads under the image."""
    runtime.stall = threading.Event()
    async with httpx.AsyncClient(base_url=live, timeout=10) as client:
        running: list[dict] = []
        reply = asyncio.create_task(_generate(client, running))
        while not runtime.requests:
            await asyncio.sleep(0.01)

        yielded = asyncio.Event()

        async def hold() -> None:
            async with client.stream("POST", "/internal/models/text/yield") as held:
                async for line in held.aiter_lines():
                    if '"yielded"' in line:
                        yielded.set()

        holding = asyncio.create_task(hold())
        await asyncio.sleep(0.2)
        unloaded_while_running = list(runtime.unloaded)
        yielded_while_running = yielded.is_set()

        runtime.stall.set()
        await reply
        await asyncio.wait_for(yielded.wait(), timeout=5)
        unloaded = list(runtime.unloaded)

        runtime.stall = None
        later: list[dict] = []
        sent_while_held = asyncio.create_task(_generate(client, later))
        await asyncio.sleep(0.2)
        reached_runtime_while_held = len(runtime.requests)

        holding.cancel()
        await asyncio.gather(holding, return_exceptions=True)
        await asyncio.wait_for(sent_while_held, timeout=5)

    assert (unloaded_while_running, yielded_while_running) == ([], False)
    assert sorted(unloaded) == sorted(runtime.models)
    assert reached_runtime_while_held == 1
    assert later[0] == {"type": "queued", "position": 1}
    assert any(frame["type"] == "text" for frame in later)


async def test_the_worker_holds_the_runtime_for_its_block(
    live: str, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What an image job or a podcast's voicing does: inside the block the text
    models are gone and local text waits; leaving it lets text through again."""
    from modules.llm.model_route.runtime_hold import text_runtime_given_up

    port = live.rsplit(":", 1)[1]
    monkeypatch.setenv("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", port)
    async with httpx.AsyncClient(base_url=live, timeout=10) as client:
        async with text_runtime_given_up():
            unloaded_inside = sorted(runtime.unloaded)
            waiting: list[dict] = []
            sent_inside = asyncio.create_task(_generate(client, waiting))
            await asyncio.sleep(0.2)
            reached_inside = len(runtime.requests)
        await asyncio.wait_for(sent_inside, timeout=5)

    assert unloaded_inside == sorted(runtime.models)
    assert reached_inside == 0
    assert any(frame["type"] == "text" for frame in waiting)
