"""In-house captcha-solver clients (vendor API glue, Apache-2.0).

Replaces the unmaintained ``captchatools`` registry. Each provider is a small
function that submits a challenge to the vendor and polls for the token;
:func:`solve` dispatches on the app-wide ``CAPTCHA_SOLVER_PROVIDER``.

Two providers are wired: **2captcha** (legacy ``in.php``/``res.php``) and
**capsolver** (AI-native ``createTask``/``getTaskResult``, materially faster on
the reCAPTCHA-*Enterprise* ``/sorry`` wall). Both express the Enterprise pieces
Google needs — the widget sitekey plus the page's dynamic ``data-s`` token
(something ``captchatools`` could not). More vendors (anticaptcha / capmonster)
are added progressively as new entries in :data:`_PROVIDERS`; until then an
unconfigured provider raises :class:`SolverUnsupportedError` so callers latch off
cleanly instead of leaking the API key to the wrong service.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

import requests

from app.utils.captcha.config import CaptchaConfig

logger = logging.getLogger(__name__)

_LOG = "[captcha][solver]"


class SolverError(Exception):
    """Base class for solver failures the caller may want to latch on."""


class SolverAuthError(SolverError):
    """Bad / unknown API key — unrecoverable without a config change."""


class SolverBalanceError(SolverError):
    """Solver account is out of balance — unrecoverable this process."""


class SolverUnsupportedError(SolverError):
    """Configured provider has no in-house client yet — unrecoverable."""


# --- 2captcha (legacy in.php/res.php) --------------------------------------

_2CAP_IN = "http://2captcha.com/in.php"
_2CAP_RES = "http://2captcha.com/res.php"
# Historical captchatools soft_id, kept so solves stay attributed on 2captcha.
_2CAP_SOFT_ID = 4782723


def proxy_login_form(proxy_url: str | None) -> str | None:
    """``http://user:pass@host:port`` -> ``user:pass@host:port`` (no scheme).

    The vendor APIs want the proxy without a scheme prefix (2captcha rejects a
    scheme with ``ERROR_PROXY_FORMAT``). Returns ``None`` for a missing or
    unparseable proxy so the solve goes proxyless rather than crashing the fetch
    (the token may then be IP-mismatched, but that fails cleanly).
    """
    if not proxy_url:
        return None
    try:
        p = urlsplit(proxy_url)
        if not p.hostname or not p.port:
            return None
        if p.username and p.password:
            return f"{p.username}:{p.password}@{p.hostname}:{p.port}"
        return f"{p.hostname}:{p.port}"
    except Exception:
        return None


def _raise_2cap(err: str) -> None:
    """Map a 2captcha error string to a typed exception (or just log a soft one)."""
    up = err.upper()
    if "ZERO_BALANCE" in up:
        raise SolverBalanceError(err)
    if "WRONG_USER_KEY" in up or "KEY_DOES_NOT_EXIST" in up:
        raise SolverAuthError(err)
    logger.warning("%s 2captcha error: %s", _LOG, err)


def _twocaptcha(
    cfg: CaptchaConfig,
    *,
    challenge_type: str,
    sitekey: str,
    page_url: str,
    proxy_url: str | None,
    user_agent: str | None,
    enterprise: bool,
    data_s: str | None,
) -> str | None:
    payload: dict = {"key": cfg.api_key, "json": 1, "soft_id": _2CAP_SOFT_ID}
    if challenge_type in ("hcaptcha", "hcap"):
        payload |= {"method": "hcaptcha", "sitekey": sitekey, "pageurl": page_url}
    elif challenge_type == "v3":
        payload |= {
            "method": "userrecaptcha",
            "version": "v3",
            "googlekey": sitekey,
            "pageurl": page_url,
            "action": cfg.v3_action,
            "min_score": cfg.v3_min_score,
        }
    else:  # v2, optionally the Enterprise variant (adds enterprise=1 + data-s)
        payload |= {
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": page_url,
        }
        if enterprise:
            payload["enterprise"] = 1
        if data_s:
            payload["data-s"] = data_s

    proxy = proxy_login_form(proxy_url)
    if proxy:
        payload["proxy"] = proxy
        payload["proxytype"] = "HTTP"
    if user_agent:
        payload["userAgent"] = user_agent

    try:
        submit = requests.post(_2CAP_IN, data=payload, timeout=30).json()
    except requests.RequestException as e:
        logger.warning("%s 2captcha submit request failed: %s", _LOG, e)
        return None
    if submit.get("status") != 1:
        _raise_2cap(str(submit.get("request", "")))
        return None

    task_id = submit["request"]
    deadline = time.monotonic() + cfg.timeout_s
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            got = requests.get(
                f"{_2CAP_RES}?key={cfg.api_key}&action=get&id={task_id}&json=1",
                timeout=30,
            ).json()
        except requests.RequestException:
            continue
        if got.get("status") == 1:
            return got["request"] or None
        req = str(got.get("request", ""))
        if req != "CAPCHA_NOT_READY":
            _raise_2cap(req)
            return None
    logger.warning("%s 2captcha solve timed out after %ss", _LOG, cfg.timeout_s)
    return None


# --- capsolver (createTask / getTaskResult) --------------------------------

_CAPSOLVER_CREATE = "https://api.capsolver.com/createTask"
_CAPSOLVER_RESULT = "https://api.capsolver.com/getTaskResult"


def capsolver_proxy(proxy_url: str | None) -> str | None:
    """``http://user:pass@host:port`` -> ``http:host:port:user:pass``.

    CapSolver's ``proxy`` field is a single colon-delimited
    ``scheme:host:port[:user:pass]`` string (NOT a URL). Returns ``None`` for a
    missing/unparseable proxy so the caller falls back to a proxyless task.
    """
    if not proxy_url:
        return None
    try:
        p = urlsplit(proxy_url)
        if not p.hostname or not p.port:
            return None
        scheme = p.scheme or "http"
        if p.username and p.password:
            return f"{scheme}:{p.hostname}:{p.port}:{p.username}:{p.password}"
        return f"{scheme}:{p.hostname}:{p.port}"
    except Exception:
        return None


def _raise_capsolver(code: str, desc: str) -> None:
    """Map a CapSolver errorCode to a typed exception (or log a soft one)."""
    up = (code or "").upper()
    if "ZERO_BALANCE" in up or "INSUFFICIENT" in up:
        raise SolverBalanceError(f"{code}: {desc}")
    if "KEY" in up:  # ERROR_KEY_DENIED_ACCESS / ERROR_KEY_DOES_NOT_EXIST
        raise SolverAuthError(f"{code}: {desc}")
    logger.warning("%s capsolver error: %s %s", _LOG, code, desc)


def _capsolver(
    cfg: CaptchaConfig,
    *,
    challenge_type: str,
    sitekey: str,
    page_url: str,
    proxy_url: str | None,
    user_agent: str | None,
    enterprise: bool,
    data_s: str | None,
) -> str | None:
    # We always egress through our own sticky proxy, so the proxied task types
    # (no "ProxyLess" casing ambiguity) are the hot path; the proxyless variants
    # are only the fallback when no proxy was threaded through.
    proxy = capsolver_proxy(proxy_url)
    has_proxy = proxy is not None
    task: dict = {"websiteURL": page_url, "websiteKey": sitekey}
    if challenge_type in ("hcaptcha", "hcap"):
        task["type"] = "HCaptchaTask" if has_proxy else "HCaptchaTaskProxyLess"
    elif challenge_type == "v3":
        base = "ReCaptchaV3EnterpriseTask" if enterprise else "ReCaptchaV3Task"
        task["type"] = base if has_proxy else base + "ProxyLess"
        task["pageAction"] = cfg.v3_action
        task["minScore"] = cfg.v3_min_score
    else:  # v2, optionally the Enterprise variant (Google /sorry)
        base = "ReCaptchaV2EnterpriseTask" if enterprise else "ReCaptchaV2Task"
        task["type"] = base if has_proxy else base + "ProxyLess"
        if data_s:
            # Enterprise carries the /anchor `s` under enterprisePayload; the
            # normal-v2 field is recaptchaDataSValue.
            task["enterprisePayload" if enterprise else "recaptchaDataSValue"] = (
                {"s": data_s} if enterprise else data_s
            )
    if has_proxy:
        task["proxy"] = proxy
    if user_agent:
        task["userAgent"] = user_agent

    try:
        created = requests.post(
            _CAPSOLVER_CREATE,
            json={"clientKey": cfg.api_key, "task": task},
            timeout=30,
        ).json()
    except requests.RequestException as e:
        logger.warning("%s capsolver createTask failed: %s", _LOG, e)
        return None
    if created.get("errorId"):
        _raise_capsolver(
            str(created.get("errorCode", "")), str(created.get("errorDescription", ""))
        )
        return None
    task_id = created.get("taskId")
    if not task_id:
        return None

    deadline = time.monotonic() + cfg.timeout_s
    while time.monotonic() < deadline:
        time.sleep(2)  # AI solver is fast; poll tighter than 2captcha's 5 s
        try:
            got = requests.post(
                _CAPSOLVER_RESULT,
                json={"clientKey": cfg.api_key, "taskId": task_id},
                timeout=30,
            ).json()
        except requests.RequestException:
            continue
        if got.get("errorId"):
            _raise_capsolver(
                str(got.get("errorCode", "")), str(got.get("errorDescription", ""))
            )
            return None
        if got.get("status") == "ready":
            return (got.get("solution") or {}).get("gRecaptchaResponse") or None
    logger.warning("%s capsolver solve timed out after %ss", _LOG, cfg.timeout_s)
    return None


# provider name (CAPTCHA_SOLVER_PROVIDER) -> client. Add vendors here.
_PROVIDERS = {"2captcha": _twocaptcha, "capsolver": _capsolver}


def supported_providers() -> list[str]:
    return sorted(_PROVIDERS)


def solve(
    cfg: CaptchaConfig,
    *,
    challenge_type: str,
    sitekey: str,
    page_url: str,
    proxy_url: str | None = None,
    user_agent: str | None = None,
    enterprise: bool = False,
    data_s: str | None = None,
) -> str | None:
    """Harvest a token from the configured solver, or ``None`` on soft failure.

    ``challenge_type`` is ``v2`` / ``v3`` / ``hcaptcha``; set ``enterprise`` +
    ``data_s`` for reCAPTCHA-v2-Enterprise pages (e.g. Google ``/sorry``). The
    solve egresses through ``proxy_url`` so the token is bound to the crawl's
    own exit IP. Raises a :class:`SolverError` subclass on unrecoverable errors
    (bad key / no balance / unsupported provider) so callers can latch.
    """
    client = _PROVIDERS.get((cfg.solving_site or "").lower())
    if client is None:
        raise SolverUnsupportedError(
            f"captcha provider {cfg.solving_site!r} has no in-house client "
            f"(supported: {supported_providers()})"
        )
    return client(
        cfg,
        challenge_type=challenge_type,
        sitekey=sitekey,
        page_url=page_url,
        proxy_url=proxy_url,
        user_agent=user_agent,
        enterprise=enterprise,
        data_s=data_s,
    )
