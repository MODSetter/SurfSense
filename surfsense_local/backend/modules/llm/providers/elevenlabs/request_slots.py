"""How many requests one ElevenLabs account has in flight from this process."""

import asyncio
import hashlib
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from shared import cancellation

__all__ = ["request_slot"]

# The smallest plan's limit, Free on v4. A larger plan gives no reason to go
# faster: Studio runs four jobs at most, and each sends one line at a time.
_SLOTS_PER_ACCOUNT = 2
_POLL_SECONDS = 0.05

_slots: dict[str, threading.BoundedSemaphore] = {}
_slots_lock = threading.Lock()


def _account_slots(base_url: str, api_key: str | None) -> threading.BoundedSemaphore:
    # A digest: this outlives the request, and the key only has to tell accounts apart.
    account = hashlib.sha256(f"{base_url}\0{api_key}".encode()).hexdigest()
    with _slots_lock:
        return _slots.setdefault(
            account, threading.BoundedSemaphore(_SLOTS_PER_ACCOUNT)
        )


@asynccontextmanager
async def request_slot(base_url: str, api_key: str | None) -> AsyncIterator[None]:
    """Hold one of the account's slots. A thread's semaphore, polled: each Studio
    job runs its own event loop on its own thread, and the API's loop must not block."""
    slots = _account_slots(base_url, api_key)
    while not slots.acquire(blocking=False):
        cancellation.raise_if_cancelled()
        await asyncio.sleep(_POLL_SECONDS)
    try:
        yield
    finally:
        slots.release()
