"""Loading a model before someone is waiting on it.

A cold load is tens of seconds, and the router evicts on an idle timer, so a
load is not something to avoid but something to move: it happens either while
the user is navigating or while they are watching a stalled answer.

Two calls, because neither answers on its own. `POST /models/load` blocks until
the model is resident but says nothing on the way, and `GET /models/sse` says
everything but never asks for anything to happen.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

import httpx

from modules.llm.providers.llamacpp.model_events import LoadProgress, watch_models
from modules.llm.providers.llamacpp.router_client import RouterClient

logger = logging.getLogger(__name__)

# What the router calls a load that finished, either way. `loaded` is the state
# the caller asked for; `unloaded` is a worker that died, and waiting past it
# would hang on a model that is never arriving.
TERMINAL = frozenset({"loaded", "unloaded"})

# How long the load itself is given once the watch has stopped. Short because
# it is not the load's budget: a terminal frame means the model is already
# resident and the request is returning, and a dead stream means nothing is
# coming. `RouterClient`'s own timeout covers the load while it is running.
SETTLE_SECONDS = 5.0


async def warm_model(
    base_url: str, model_id: str, *, transport: httpx.BaseTransport | None = None
) -> AsyncIterator[LoadProgress]:
    """Bring `model_id` into memory, reporting progress until it is there.

    Best effort by design: a warm that fails costs the wait it was trying to
    avoid, which is where the caller already was. It never raises, because
    nothing downstream of an install should fail over an optimisation.
    """
    client = RouterClient(base_url, transport=transport)
    # Started before the watch, because the POST is what produces the frames to
    # watch. It is not awaited here: the call blocks until the model is
    # resident, which is the whole wait this exists to report on.
    loading = asyncio.create_task(client.load(model_id))
    try:
        async for progress in watch_models(base_url, transport=transport):
            # One stream carries every model. `--models-max 1` means another
            # model's load is this one being evicted, which must not be
            # reported as progress toward it.
            if progress.model_id != model_id:
                continue
            yield progress
            if progress.status in TERMINAL:
                return
    except httpx.HTTPError as error:
        # The sidecar going away mid-watch is routine: a preset rewrite
        # restarts it. The model is still on disk and still loads on demand.
        logger.info("stopped watching %s while warming: %s", model_id, error)
    finally:
        await _settle(loading, model_id)


async def _settle(loading: asyncio.Task, model_id: str) -> None:
    """Let the load finish and report its own failure, or stop waiting on it.

    Awaited rather than cancelled outright, because a watch that reached a
    terminal frame first would otherwise cancel the very request that produced
    it, and a load never issued is a warm that did nothing. Bounded, because by
    the time this runs the load has either finished or the stream it was
    reporting through has gone.

    A task dropped without this logs `Task exception was never retrieved` at
    whatever point the loop collects it, which is a traceback with no request
    attached to it.
    """
    try:
        await asyncio.wait_for(loading, SETTLE_SECONDS)
    except (TimeoutError, asyncio.CancelledError):
        pass
    except (httpx.HTTPError, OSError) as error:
        logger.info("could not warm %s: %s", model_id, error)
