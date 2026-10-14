from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from modules.llm.model_route.api_address import ApiNotRunningError, api_url
from modules.llm.providers.llamacpp.router_client import RouterClient
from modules.llm.providers.llamacpp.unload import unload_text_models
from modules.llm.providers.sse_lines import sse_lines
from shared.config import get_llm_settings

# Long enough to wait for running replies to finish before the hold is granted,
# which keep-alives arrive throughout.
SILENCE_SECONDS = 60.0


@asynccontextmanager
async def text_runtime_given_up() -> AsyncIterator[None]:
    """Hold the local text runtime unloaded through the API, for the block.

    The API lets running replies finish first and keeps new ones waiting until
    this request closes, which leaving the block, or this process dying, does.
    A process run without an API, by hand or under test, has nothing generating
    beside it to wait for, so it unloads the text models itself.
    """
    try:
        url = api_url()
    except ApiNotRunningError:
        await unload_text_models(RouterClient(get_llm_settings().llamacpp_base_url))
        yield
        return
    timeout = httpx.Timeout(SILENCE_SECONDS, connect=5.0)
    async with (
        httpx.AsyncClient(timeout=timeout) as client,
        client.stream("POST", f"{url}/internal/models/text/yield") as held,
    ):
        held.raise_for_status()
        lines = sse_lines(held)
        async for line in lines:
            if '"yielded"' in line:
                break
        else:
            raise httpx.RemoteProtocolError(
                "the API closed the hold before granting it"
            )
        yield
