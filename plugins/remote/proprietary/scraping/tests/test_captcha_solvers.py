"""Offline checks for the in-house captcha-solver seam.

The network solve can't be unit-tested, but the boundary logic can: a wrong
proxy reformat (2captcha's ``ERROR_PROXY_FORMAT``) or dispatching to a provider
we haven't wired silently burns paid solves / leaks the key to the wrong vendor.
"""

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from host.tests.serving import serving
from proprietary.scraping.captcha import solvers
from proprietary.scraping.captcha.config import CaptchaConfig


def _cfg(**overrides: Any) -> CaptchaConfig:
    base: dict[str, Any] = {
        "provider": "2captcha",
        "api_key": "key-123",
        "timeout_s": 30,
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


async def test_unsupported_provider_raises_solvererror():
    # An unconfigured provider must fail loudly (latch) rather than POST the key
    # to a wired vendor's endpoint under the wrong account.
    with pytest.raises(solvers.SolverUnsupportedError):
        await solvers.solve(
            _cfg(provider="anticaptcha"),
            challenge_type="v2",
            sitekey="SK",
            page_url="https://t.test",
        )
    assert issubclass(solvers.SolverUnsupportedError, solvers.SolverError)


def test_wired_providers_are_registered():
    supported = solvers.supported_providers()
    assert "2captcha" in supported
    assert "capsolver" in supported


# --- a solve, against a stand-in vendor on loopback -------------------------


class StandInCapsolver:
    """Ready on the second poll, or out of balance."""

    def __init__(self, *, balance: bool = True) -> None:
        self.balance = balance
        self.polls = 0
        self.tasks: list[dict] = []
        # The client port of each request: one port is one kept connection.
        self.ports: list[int] = []
        self.app = Starlette(
            routes=[
                Route("/createTask", self._create, methods=["POST"]),
                Route("/getTaskResult", self._result, methods=["POST"]),
            ]
        )

    async def _create(self, request: Request) -> JSONResponse:
        self.ports.append(request.client.port if request.client else 0)
        if not self.balance:
            return JSONResponse(
                {
                    "errorId": 1,
                    "errorCode": "ERROR_ZERO_BALANCE",
                    "errorDescription": "",
                }
            )
        self.tasks.append((await request.json())["task"])
        return JSONResponse({"errorId": 0, "taskId": "t-1"})

    async def _result(self, request: Request) -> JSONResponse:
        self.ports.append(request.client.port if request.client else 0)
        self.polls += 1
        if self.polls < 2:
            return JSONResponse({"errorId": 0, "status": "processing"})
        solution = {"gRecaptchaResponse": "token-1"}
        return JSONResponse({"errorId": 0, "status": "ready", "solution": solution})


@pytest.fixture
def capsolver(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[StandInCapsolver], StandInCapsolver]]:
    """Points the solver at a stand-in vendor, served for the test's length."""
    with ExitStack() as stack:

        def at(vendor: StandInCapsolver) -> StandInCapsolver:
            url = stack.enter_context(serving(vendor.app))
            monkeypatch.setattr(solvers, "_CAPSOLVER_CREATE", f"{url}/createTask")
            monkeypatch.setattr(solvers, "_CAPSOLVER_RESULT", f"{url}/getTaskResult")
            monkeypatch.setattr(solvers, "_CAPSOLVER_POLL_SECONDS", 0.01)
            return vendor

        yield at


async def test_an_enterprise_solve_goes_through_the_sticky_proxy(capsolver):
    """Google's /sorry token is bound to the IP, so the vendor solves through ours."""
    vendor = capsolver(StandInCapsolver())

    token = await solvers.solve(
        _cfg(provider="capsolver"),
        challenge_type="v2",
        sitekey="SK",
        page_url="https://www.google.com/sorry/index",
        proxy_url="http://user:pass@gw.dataimpulse.com:823",  # pragma: allowlist secret
        enterprise=True,
        data_s="ds-1",
    )

    assert token == "token-1"
    assert vendor.tasks[0]["type"] == "ReCaptchaV2EnterpriseTask"
    assert vendor.tasks[0]["proxy"] == "http:gw.dataimpulse.com:823:user:pass"
    assert vendor.tasks[0]["enterprisePayload"] == {"s": "ds-1"}


async def test_a_solve_keeps_one_connection_for_the_task_and_its_polls(capsolver):
    """A new connection per poll paid a TLS handshake each time."""
    vendor = capsolver(StandInCapsolver())

    await solvers.solve(
        _cfg(provider="capsolver"),
        challenge_type="v2",
        sitekey="SK",
        page_url="https://www.google.com/sorry/index",
    )

    assert len(vendor.ports) == 3
    assert len(set(vendor.ports)) == 1


async def test_no_balance_is_an_error_the_caller_latches_on(capsolver):
    capsolver(StandInCapsolver(balance=False))

    with pytest.raises(solvers.SolverBalanceError):
        await solvers.solve(
            _cfg(provider="capsolver"),
            challenge_type="v2",
            sitekey="SK",
            page_url="https://www.google.com/sorry/index",
        )
