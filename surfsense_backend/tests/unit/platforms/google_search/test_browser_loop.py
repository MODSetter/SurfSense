"""The Windows regression this guards: main.py runs the server on a
SelectorEventLoop (psycopg needs it), and Selector loops cannot spawn
subprocesses — so patchright's Chromium launch died with NotImplementedError
on every render. fetch.py now marshals all browser work onto a dedicated
subprocess-capable loop; this check proves that marshalling works from a
Selector main loop without paying for a real browser launch.
"""

import asyncio
import sys

import pytest

from app.proprietary.platforms.google_search import fetch


def test_browser_loop_can_spawn_subprocess_from_selector_loop():
    async def spawn():
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "print('ok')",
            stdout=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        return out

    async def main():
        if sys.platform == "win32":
            # The original bug: the server's own loop cannot do this.
            with pytest.raises(NotImplementedError):
                await spawn()
        # The fix: the same work marshalled onto the browser loop succeeds.
        assert b"ok" in await fetch._in_browser_loop(spawn())

    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
