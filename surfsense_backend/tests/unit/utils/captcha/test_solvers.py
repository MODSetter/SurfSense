"""Offline checks for the in-house captcha-solver seam.

The network solve can't be unit-tested, but the boundary logic can: a wrong
proxy reformat (2captcha's ``ERROR_PROXY_FORMAT``) or dispatching to a provider
we haven't wired silently burns paid solves / leaks the key to the wrong vendor.
"""

import pytest

from app.utils.captcha import solvers
from app.utils.captcha.config import CaptchaConfig

pytestmark = pytest.mark.unit


def _cfg(**overrides) -> CaptchaConfig:
    base = {
        "enabled": True,
        "solving_site": "2captcha",
        "api_key": "key-123",
        "max_attempts_per_url": 1,
        "timeout_s": 30,
        "captcha_type_default": "v2",
        "v3_min_score": 0.7,
        "v3_action": "verify",
    }
    base.update(overrides)
    return CaptchaConfig(**base)


# --- proxy reformat (2captcha wants login:pass@host:port, NO scheme) --------


def test_proxy_login_form_strips_scheme():
    got = solvers.proxy_login_form("http://user:pass@gw.dataimpulse.com:15673")
    assert got == "user:pass@gw.dataimpulse.com:15673"


def test_proxy_login_form_without_credentials():
    assert (
        solvers.proxy_login_form("http://gw.dataimpulse.com:823")
        == "gw.dataimpulse.com:823"
    )


def test_proxy_login_form_none_on_missing_or_bad():
    assert solvers.proxy_login_form(None) is None
    assert solvers.proxy_login_form("not a url") is None


# --- capsolver proxy reformat (colon-delimited scheme:host:port:user:pass) --


def test_capsolver_proxy_colon_delimited_with_creds():
    got = solvers.capsolver_proxy("http://user:pass@gw.dataimpulse.com:823")
    assert got == "http:gw.dataimpulse.com:823:user:pass"


def test_capsolver_proxy_without_credentials():
    assert (
        solvers.capsolver_proxy("http://gw.dataimpulse.com:823")
        == "http:gw.dataimpulse.com:823"
    )


def test_capsolver_proxy_none_on_missing_or_bad():
    assert solvers.capsolver_proxy(None) is None
    assert solvers.capsolver_proxy("not a url") is None


# --- dispatch --------------------------------------------------------------


def test_unsupported_provider_raises_solvererror():
    # An unconfigured provider must fail loudly (latch) rather than POST the key
    # to a wired vendor's endpoint under the wrong account.
    with pytest.raises(solvers.SolverUnsupportedError):
        solvers.solve(
            _cfg(solving_site="anticaptcha"),
            challenge_type="v2",
            sitekey="SK",
            page_url="https://t.test",
        )
    assert issubclass(solvers.SolverUnsupportedError, solvers.SolverError)


def test_wired_providers_are_registered():
    supported = solvers.supported_providers()
    assert "2captcha" in supported
    assert "capsolver" in supported
