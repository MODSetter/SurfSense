"""The captcha page_action's glue: detection, proxy pass-through, attempt counting, the per-URL cap, the latch.

The page and the solver are faked; the vendor clients are tested in ``proprietary.scraping``.
"""

import asyncio

import pytest

from proprietary.scraping.captcha import CaptchaConfig
from proprietary.web_crawl import captcha as cap


def _cfg(**overrides) -> CaptchaConfig:
    base = {
        "provider": "capsolver",
        "api_key": "key-123",
        "timeout_s": 30,
        "v3_min_score": 0.7,
        "v3_action": "verify",
    }
    base.update(overrides)
    return CaptchaConfig(**base)


class _FakeEl:
    def __init__(self, attrs: dict[str, str]):
        self._attrs = attrs

    async def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)


class _FakePage:
    """Minimal async-Playwright-ish page for detection/injection tests."""

    def __init__(
        self, widgets=None, iframes=None, scripts=None, url="https://t.test/p"
    ):
        self._widgets = widgets or {}  # selector -> _FakeEl
        self._iframes = iframes or []  # list[_FakeEl]
        self._scripts = scripts or []  # list[_FakeEl]
        self.url = url
        self.evaluated: list = []

    async def query_selector(self, selector: str):
        return self._widgets.get(selector)

    async def query_selector_all(self, selector: str):
        if selector == "iframe[src]":
            return self._iframes
        if selector == "script[src]":
            return self._scripts
        return []

    async def evaluate(self, js, arg=None):
        self.evaluated.append((js, arg))
        if "navigator.userAgent" in js:
            return "UA/1.0"
        return None

    async def wait_for_load_state(self, *_a, **_k):
        return None


@pytest.fixture(autouse=True)
def _clear_latch():
    cap.reset_solver_latch()
    yield
    cap.reset_solver_latch()


# --- detection -------------------------------------------------------------


class TestDetect:
    async def test_recaptcha_v2_widget(self):
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK_V2"})}
        )
        assert await cap.detect_challenge(page) == ("v2", "SK_V2")

    async def test_hcaptcha_widget(self):
        page = _FakePage(
            widgets={".h-captcha[data-sitekey]": _FakeEl({"data-sitekey": "SK_H"})}
        )
        assert await cap.detect_challenge(page) == ("hcaptcha", "SK_H")

    async def test_iframe_fallback(self):
        page = _FakePage(
            iframes=[_FakeEl({"src": "https://www.google.com/recaptcha/api2?k=SK_IF"})]
        )
        assert await cap.detect_challenge(page) == ("v2", "SK_IF")

    async def test_v3_render_param_when_default_v3(self):
        page = _FakePage(
            scripts=[
                _FakeEl({"src": "https://www.google.com/recaptcha/api.js?render=SK_V3"})
            ]
        )
        assert await cap.detect_challenge(page, "v3") == (
            "v3",
            "SK_V3",
        )

    async def test_no_challenge(self):
        assert await cap.detect_challenge(_FakePage()) is None


# --- factory / page_action -------------------------------------------------


class TestFactoryGating:
    def test_returns_none_without_a_key(self):
        state = {"attempts": 0, "solved": False}
        assert build_action(state, _cfg(api_key=None)) is None

    def test_returns_none_when_latched(self):
        cap._latch_solver("test")
        state = {"attempts": 0, "solved": False}
        assert build_action(state, _cfg()) is None


def build_action(state, cfg, proxy="http://u:p@1.2.3.4:9000", **kwargs):
    return cap.build_captcha_page_action(state, proxy, cfg, **kwargs)


class TestPageAction:
    async def test_solves_and_records(self, monkeypatch):
        captured = {}

        async def _fake_harvest(cfg, ctype, sitekey, page_url, proxy, ua):
            captured.update(
                ctype=ctype, sitekey=sitekey, page_url=page_url, proxy=proxy, ua=ua
            )
            return "TOKEN"

        injected = {}
        monkeypatch.setattr(cap, "_harvest_token", _fake_harvest)

        async def _inject(page, ctype, token):
            injected.update(ctype=ctype, token=token)

        monkeypatch.setattr(cap, "_inject_and_submit", _inject)

        state = {"attempts": 0, "solved": False}
        action = build_action(state, _cfg())
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        await action(page)

        assert state == {"attempts": 1, "solved": True}
        # Solver egressed from the crawl's proxy (raw URL; the seam reformats
        # per vendor), with the page UA.
        assert captured["proxy"] == "http://u:p@1.2.3.4:9000"
        assert captured["ua"] == "UA/1.0"
        assert captured["ctype"] == "v2"
        assert injected == {"ctype": "v2", "token": "TOKEN"}

    async def test_no_challenge_no_attempt(self, monkeypatch):
        async def _never(*_a, **_k):
            pytest.fail("should not solve")

        monkeypatch.setattr(cap, "_harvest_token", _never)
        state = {"attempts": 0, "solved": False}
        await build_action(state, _cfg())(_FakePage())
        assert state == {"attempts": 0, "solved": False}

    async def test_per_url_attempt_cap(self, monkeypatch):
        calls = {"n": 0}

        async def _h(*_a, **_k):
            calls["n"] += 1
            return "TOKEN"

        async def _inject(*_a, **_k):
            return None

        monkeypatch.setattr(cap, "_harvest_token", _h)
        monkeypatch.setattr(cap, "_inject_and_submit", _inject)

        # Already at the cap → no further solve.
        state = {"attempts": 1, "solved": False}
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        await build_action(state, _cfg(), max_attempts=1)(page)
        assert calls["n"] == 0
        assert state["attempts"] == 1

    async def test_empty_token_counts_attempt_but_not_solved(self, monkeypatch):
        async def _empty(*_a, **_k):
            return None

        async def _no_inject(*_a, **_k):
            pytest.fail("no inject")

        monkeypatch.setattr(cap, "_harvest_token", _empty)
        monkeypatch.setattr(cap, "_inject_and_submit", _no_inject)
        state = {"attempts": 0, "solved": False}
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        await build_action(state, _cfg())(page)
        assert state == {"attempts": 1, "solved": False}

    async def test_no_balance_latches_and_stops(self, monkeypatch):
        class NoBalanceError(Exception):
            pass

        async def _boom(*_a, **_k):
            raise NoBalanceError("out of balance")

        monkeypatch.setattr(cap, "_harvest_token", _boom)
        state = {"attempts": 0, "solved": False}
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        await build_action(state, _cfg(), max_attempts=3)(page)

        # Attempt counted, not solved, and the process latch is tripped so the
        # next factory build refuses to wire solving at all (no retry loop).
        assert state == {"attempts": 1, "solved": False}
        assert cap.solver_latched() is True
        assert build_action({"attempts": 0, "solved": False}, _cfg()) is None

    async def test_a_slow_solve_is_abandoned_at_the_timeout(self, monkeypatch):
        async def _slow(*_a, **_k):
            await asyncio.sleep(5)
            return "TOKEN"

        monkeypatch.setattr(cap, "_harvest_token", _slow)
        state = {"attempts": 0, "solved": False}
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        await build_action(state, _cfg(timeout_s=0))(page)
        assert state == {"attempts": 1, "solved": False}
        assert cap.solver_latched() is False
