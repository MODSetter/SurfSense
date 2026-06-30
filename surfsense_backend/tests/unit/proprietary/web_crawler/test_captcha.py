"""Unit tests for the proprietary captcha page_action factory (Phase 3d).

The browser/solver boundary is mocked: a fake Playwright ``page`` and a
monkeypatched ``_harvest_token`` / injection. We assert the glue logic —
detection, proxy reformatting, attempt counting + state surfacing, the per-URL
cap, and the no-balance process latch.
"""

import pytest

from app.proprietary.web_crawler import captcha as cap
from app.utils.captcha import CaptchaConfig

pytestmark = pytest.mark.unit


def _cfg(**overrides) -> CaptchaConfig:
    base = dict(
        enabled=True,
        solving_site="capsolver",
        api_key="key-123",
        max_attempts_per_url=1,
        timeout_s=30,
        captcha_type_default="v2",
        v3_min_score=0.7,
        v3_action="verify",
    )
    base.update(overrides)
    return CaptchaConfig(**base)


class _FakeEl:
    def __init__(self, attrs: dict[str, str]):
        self._attrs = attrs

    def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)


class _FakePage:
    """Minimal sync-Playwright-ish page for detection/injection tests."""

    def __init__(self, widgets=None, iframes=None, scripts=None, url="https://t.test/p"):
        self._widgets = widgets or {}  # selector -> _FakeEl
        self._iframes = iframes or []  # list[_FakeEl]
        self._scripts = scripts or []  # list[_FakeEl]
        self.url = url
        self.evaluated: list = []

    def query_selector(self, selector: str):
        return self._widgets.get(selector)

    def query_selector_all(self, selector: str):
        if selector == "iframe[src]":
            return self._iframes
        if selector == "script[src]":
            return self._scripts
        return []

    def evaluate(self, js, arg=None):
        self.evaluated.append((js, arg))
        if "navigator.userAgent" in js:
            return "UA/1.0"
        return None

    def wait_for_load_state(self, *_a, **_k):
        return None


@pytest.fixture(autouse=True)
def _clear_latch():
    cap.reset_solver_latch()
    yield
    cap.reset_solver_latch()


# --- proxy reformat --------------------------------------------------------


class TestProxyReformat:
    def test_with_auth(self):
        assert (
            cap.proxy_url_to_captchatools("http://user:pass@1.2.3.4:8080")
            == "1.2.3.4:8080:user:pass"
        )

    def test_without_auth(self):
        assert cap.proxy_url_to_captchatools("http://1.2.3.4:8080") == "1.2.3.4:8080"

    def test_none_and_garbage(self):
        assert cap.proxy_url_to_captchatools(None) is None
        assert cap.proxy_url_to_captchatools("not-a-url") is None


# --- detection -------------------------------------------------------------


class TestDetect:
    def test_recaptcha_v2_widget(self):
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK_V2"})}
        )
        assert cap.detect_challenge(page, _cfg()) == ("v2", "SK_V2")

    def test_hcaptcha_widget(self):
        page = _FakePage(
            widgets={".h-captcha[data-sitekey]": _FakeEl({"data-sitekey": "SK_H"})}
        )
        assert cap.detect_challenge(page, _cfg()) == ("hcaptcha", "SK_H")

    def test_iframe_fallback(self):
        page = _FakePage(
            iframes=[_FakeEl({"src": "https://www.google.com/recaptcha/api2?k=SK_IF"})]
        )
        assert cap.detect_challenge(page, _cfg()) == ("v2", "SK_IF")

    def test_v3_render_param_when_default_v3(self):
        page = _FakePage(
            scripts=[_FakeEl({"src": "https://www.google.com/recaptcha/api.js?render=SK_V3"})]
        )
        assert cap.detect_challenge(page, _cfg(captcha_type_default="v3")) == (
            "v3",
            "SK_V3",
        )

    def test_no_challenge(self):
        assert cap.detect_challenge(_FakePage(), _cfg()) is None


# --- factory / page_action -------------------------------------------------


class TestFactoryGating:
    def test_returns_none_when_disabled(self):
        state = {"attempts": 0, "solved": False}
        assert build_action(state, _cfg(enabled=False)) is None

    def test_returns_none_when_latched(self):
        cap._latch_solver("test")
        state = {"attempts": 0, "solved": False}
        assert build_action(state, _cfg()) is None


def build_action(state, cfg, proxy="http://u:p@1.2.3.4:9000"):
    return cap.build_captcha_page_action(state, proxy, cfg)


class TestPageAction:
    def test_solves_and_records(self, monkeypatch):
        captured = {}

        def _fake_harvest(cfg, ctype, sitekey, page_url, proxy, ua):
            captured.update(
                ctype=ctype, sitekey=sitekey, page_url=page_url, proxy=proxy, ua=ua
            )
            return "TOKEN"

        injected = {}
        monkeypatch.setattr(cap, "_harvest_token", _fake_harvest)
        monkeypatch.setattr(
            cap,
            "_inject_and_submit",
            lambda page, ctype, token: injected.update(ctype=ctype, token=token),
        )

        state = {"attempts": 0, "solved": False}
        action = build_action(state, _cfg())
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        action(page)

        assert state == {"attempts": 1, "solved": True}
        # Solver egressed from the crawl's proxy, reformatted, with the page UA.
        assert captured["proxy"] == "1.2.3.4:9000:u:p"
        assert captured["ua"] == "UA/1.0"
        assert captured["ctype"] == "v2"
        assert injected == {"ctype": "v2", "token": "TOKEN"}

    def test_no_challenge_no_attempt(self, monkeypatch):
        monkeypatch.setattr(
            cap, "_harvest_token", lambda *a, **k: pytest.fail("should not solve")
        )
        state = {"attempts": 0, "solved": False}
        build_action(state, _cfg())(_FakePage())
        assert state == {"attempts": 0, "solved": False}

    def test_per_url_attempt_cap(self, monkeypatch):
        calls = {"n": 0}

        def _h(*_a, **_k):
            calls["n"] += 1
            return "TOKEN"

        monkeypatch.setattr(cap, "_harvest_token", _h)
        monkeypatch.setattr(cap, "_inject_and_submit", lambda *a, **k: None)

        # Already at the cap → no further solve.
        state = {"attempts": 1, "solved": False}
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        build_action(state, _cfg(max_attempts_per_url=1))(page)
        assert calls["n"] == 0
        assert state["attempts"] == 1

    def test_empty_token_counts_attempt_but_not_solved(self, monkeypatch):
        monkeypatch.setattr(cap, "_harvest_token", lambda *a, **k: None)
        monkeypatch.setattr(
            cap, "_inject_and_submit", lambda *a, **k: pytest.fail("no inject")
        )
        state = {"attempts": 0, "solved": False}
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        build_action(state, _cfg())(page)
        assert state == {"attempts": 1, "solved": False}

    def test_no_balance_latches_and_stops(self, monkeypatch):
        class ErrNoBalance(Exception):
            pass

        def _boom(*_a, **_k):
            raise ErrNoBalance("out of balance")

        monkeypatch.setattr(cap, "_harvest_token", _boom)
        state = {"attempts": 0, "solved": False}
        page = _FakePage(
            widgets={".g-recaptcha[data-sitekey]": _FakeEl({"data-sitekey": "SK"})}
        )
        build_action(state, _cfg(max_attempts_per_url=3))(page)

        # Attempt counted, not solved, and the process latch is tripped so the
        # next factory build refuses to wire solving at all (no retry loop).
        assert state == {"attempts": 1, "solved": False}
        assert cap.solver_latched() is True
        assert build_action({"attempts": 0, "solved": False}, _cfg()) is None
