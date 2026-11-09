"""Process-wide, subprocess-capable event loop for browser work.

patchright launches Chromium via ``asyncio.create_subprocess_exec``, which the
server's main loop cannot do on Windows (main.py pins a SelectorEventLoop for
psycopg; Selector loops raise NotImplementedError on subprocess_exec). All
browser work (scrapling stealth sessions across the scrapers) therefore runs
on ONE dedicated background loop that is explicitly subprocess-capable;
callers await it across threads. This also lets persistent sessions survive
across fetches — the sync-fetcher-in-a-thread pattern would tear the browser
down every time.
"""

from __future__ import annotations

import asyncio
import sys
import threading

_browser_loop: asyncio.AbstractEventLoop | None = None
_browser_loop_guard = threading.Lock()


def get_browser_loop() -> asyncio.AbstractEventLoop:
    """The lazily-started, process-wide event loop all browser work runs on."""
    global _browser_loop
    with _browser_loop_guard:
        if _browser_loop is None:
            loop = (
                asyncio.ProactorEventLoop()
                if sys.platform == "win32"
                else asyncio.new_event_loop()
            )
            threading.Thread(
                target=loop.run_forever, name="browser-loop", daemon=True
            ).start()
            _browser_loop = loop
        return _browser_loop


async def in_browser_loop(coro):
    """Run ``coro`` on the browser loop and await its result from this loop."""
    return await asyncio.wrap_future(
        asyncio.run_coroutine_threadsafe(coro, get_browser_loop())
    )
