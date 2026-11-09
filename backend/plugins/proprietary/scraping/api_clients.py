"""Kept HTTP clients for the vendor APIs the plugins call: captcha solvers, SearXNG, Keygen.

A new client pays a TLS handshake on every request (measured 150-250 ms against
CapSolver, 107-114 ms on a kept one). A client belongs to the event loop that made
it, and the captcha solves run on the browser loop, so each loop has its own.
"""

import asyncio
import logging

import httpx2

from proprietary.scraping.lifecycle import at_shutdown

logger = logging.getLogger(__name__)

# The default for a request that names none; pass `timeout=` per request for another.
TIMEOUT_SECONDS = 30.0
# Longer than httpx's 5 s, so a vendor polled every few seconds keeps its connection;
# shorter than the servers' own idle limits.
KEEPALIVE_SECONDS = 30.0
# How long shutdown waits for a client on another loop to close.
CLOSE_SECONDS = 5.0

_clients: dict[tuple[asyncio.AbstractEventLoop, str], httpx2.AsyncClient] = {}


def api_client(base_url: str) -> httpx2.AsyncClient:
    """The kept client for `base_url` on the running loop, made on first use.

    Requests may give a path relative to `base_url` or a whole URL. Never close
    it: the host closes every kept client at shutdown.
    """
    loop = asyncio.get_running_loop()
    base = base_url.rstrip("/")
    client = _clients.get((loop, base))
    if client is None or client.is_closed:
        # A test's or a stopped server's loop is gone; its clients cannot be reused.
        # Copied first: the browser loop's thread may add a client meanwhile.
        for gone in [key for key in list(_clients) if key[0].is_closed()]:
            _clients.pop(gone, None)
        client = httpx2.AsyncClient(
            base_url=base,
            timeout=TIMEOUT_SECONDS,
            # httpx's own connection limits, with a longer keep-alive.
            limits=httpx2.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=KEEPALIVE_SECONDS,
            ),
        )
        _clients[(loop, base)] = client
        at_shutdown(close_clients)
    return client


async def close_clients() -> None:
    """Close every kept client, each on its own loop; one failing never skips the rest."""
    running = asyncio.get_running_loop()
    clients = list(_clients.items())
    _clients.clear()
    for (loop, base), client in clients:
        try:
            if loop is running:
                await client.aclose()
            elif loop.is_running():
                closing = asyncio.run_coroutine_threadsafe(client.aclose(), loop)
                await asyncio.wait_for(asyncio.wrap_future(closing), CLOSE_SECONDS)
        except Exception:
            logger.warning("[scraping] closing the client for %s failed", base)
