import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from modules.llm.admission.cost import request_cost
from modules.llm.admission.pool import AdmissionPool, Priority
from modules.llm.providers.llamacpp.router_client import RouterClient
from modules.llm.providers.types import Message
from shared.config import get_llm_settings


class LocalAdmission:
    """One admission pool per model the local runtime loads.

    In router mode each loaded model is its own child with its own cache, so
    each gets its own pool. A pool's slots and budget are what llama-server
    reports it allocated, read again whenever the pool is idle, since a reload
    can change both.
    """

    def __init__(self) -> None:
        self._pools: dict[str, AdmissionPool] = {}
        self._refreshing: dict[str, asyncio.Lock] = {}
        self._given_up = 0

    @asynccontextmanager
    async def given_up(self) -> AsyncIterator[None]:
        """Hold the runtime with no text generating, for local image generation.

        New text waits in line; what is running finishes first, so nothing is
        cut off when the text models are unloaded. Released when the block ends.
        """
        self._given_up += 1
        try:
            for pool in self._pools.values():
                pool.pause()
            for pool in list(self._pools.values()):
                await pool.drained()
            yield
        finally:
            self._given_up -= 1
            if not self._given_up:
                for pool in self._pools.values():
                    pool.resume()

    @asynccontextmanager
    async def admitted(
        self,
        model: str,
        messages: list[Message],
        max_tokens: int | None,
        priority: Priority,
        on_position: Callable[[int], None] | None = None,
    ) -> AsyncIterator[None]:
        """Hold the model's room for one generation, waiting in line for it."""
        pool = await self._pool(model)
        cost = request_cost(messages, max_tokens, budget=pool.budget, slots=pool.slots)
        async with pool.admitted(cost, priority, on_position):
            yield

    async def _pool(self, model: str) -> AdmissionPool:
        # One refresh at a time per model: requests arriving together would
        # otherwise each make a pool, and none would count the others. The
        # caller takes room or joins the line before its next await, so the
        # pool is no longer idle when the next request gets the lock.
        async with self._refreshing.setdefault(model, asyncio.Lock()):
            pool = self._pools.get(model)
            if pool is not None and (not pool.idle or self._given_up):
                return pool
            slots, budget = await _allocated(model)
            if pool is None or (pool.slots, pool.budget) != (slots, budget):
                # Only an idle pool is replaced, so nobody holds room in the old one.
                pool = AdmissionPool(slots, budget)
                if self._given_up:
                    pool.pause()
                self._pools[model] = pool
            return pool


async def _allocated(model: str) -> tuple[int, int | None]:
    """The slots and cache tokens llama-server reports for this model.

    A model not loaded yet reports nothing; it is counted as one slot of
    unknown size, which is what the runtime served before slots existed.
    """
    props = await RouterClient(get_llm_settings().llamacpp_base_url).props(model)
    slots = props.get("total_slots")
    n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx")
    return (
        slots if isinstance(slots, int) and slots > 0 else 1,
        n_ctx if isinstance(n_ctx, int) and n_ctx > 0 else None,
    )
