"""From a file on disk to a model that answers: listed by the router, then loaded,
so the first question does not pay a cold load.
"""

import asyncio
import time
from collections.abc import AsyncIterator

import httpx

from modules.llm.catalog.local.engines.engine import InstallStep
from modules.llm.providers.llamacpp import RouterClient, warm_model

# The runtime names its load stages; these are what a person reads.
_LOADING_MESSAGES = {
    "text_model": "Loading the model",
    "mmproj_model": "Loading image support",
    "spec_model": "Loading the draft model",
}
NOT_YET = "Downloaded. It becomes available once the runtime restarts."


async def wait_until_servable(
    runtime_url: str, model_id: str, *, timeout: float = 30.0, interval: float = 0.5
) -> bool:
    """Block until the restarted router lists the model. False on timeout: the
    download succeeded, and the model is usable once the sidecar is back."""
    deadline = time.monotonic() + timeout
    client = RouterClient(runtime_url)
    while time.monotonic() < deadline:
        try:
            if any(m.id == model_id for m in await client.models()):
                return True
        except httpx.HTTPError:
            pass  # restarting, which is exactly what we are waiting for
        await asyncio.sleep(interval)
    return False


async def become_ready(runtime_url: str, model_id: str) -> AsyncIterator[InstallStep]:
    yield InstallStep("preparing", "Preparing the model runtime")
    if not await wait_until_servable(runtime_url, model_id):
        yield InstallStep("complete", NOT_YET)
        return
    async for step in warm_model(runtime_url, model_id):
        yield InstallStep(
            "preparing",
            _LOADING_MESSAGES.get(step.stage or "", "Loading the model"),
            step.value,
        )
    yield InstallStep("complete", "Model is ready")
