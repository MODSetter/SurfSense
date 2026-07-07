"""The production regression this guards: several scrape runs render SERPs
concurrently on the shared browser. When one render failed, `_drop_session`
closed the browser immediately — under the sibling renders — so every
in-flight fetch died with TargetClosedError and the runs cascaded into
"exhausted 24 IPs". The drop must defer the actual close until the last
in-flight render on that session finishes.
"""

import asyncio

from app.proprietary.platforms.google_search import fetch


class _FakeSession:
    def __init__(self):
        self.release = asyncio.Event()
        self.closed = 0

    async def fetch(self, url, proxy=None):
        await self.release.wait()
        return "page"

    async def close(self):
        self.closed += 1


def test_drop_defers_close_until_inflight_renders_finish(monkeypatch):
    session = _FakeSession()

    async def fake_get_session(mobile):
        return session

    monkeypatch.setattr(fetch, "_get_session", fake_get_session)
    monkeypatch.setitem(fetch._sessions, False, session)

    async def main():
        render = asyncio.create_task(fetch._render_on_loop("u", None, False))
        await asyncio.sleep(0)  # let the render register as in-flight
        assert fetch._inflight[session] == 1

        await fetch._drop_session_on_loop(False)
        assert session.closed == 0, "must not close under an in-flight render"
        assert session in fetch._doomed
        assert False not in fetch._sessions  # next fetch relaunches

        session.release.set()
        assert await render == "page"
        assert session.closed == 1, "last render out closes the doomed browser"
        assert session not in fetch._inflight
        assert session not in fetch._doomed

    asyncio.run(main())


def test_drop_closes_immediately_when_idle():
    session = _FakeSession()

    async def main():
        fetch._sessions[False] = session
        await fetch._drop_session_on_loop(False)
        assert session.closed == 1

    asyncio.run(main())
