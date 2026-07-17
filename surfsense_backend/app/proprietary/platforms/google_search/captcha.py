"""reCAPTCHA-Enterprise solve for Google's ``/sorry`` interstitial.

Google walls a full browser's JS-driven ``sei`` reload by 302-ing it to
``/sorry/index`` — a reCAPTCHA **Enterprise** challenge. A curl-vetted IP still
hits this because the wall is on the *browser access pattern*, not the IP (curl
never runs the JS reload, so it only ever sees the useless no-JS shell). The
only way to keep rendering real SERPs on our own browser is to solve that
challenge.

This runs inside the render's async ``page_action``: when the page lands on
``/sorry``, it harvests a token from the configured solver (egressing from the
**same sticky proxy** as the browser, so the token is IP-bound), injects it, and
submits the form. Google then issues a ``GOOGLE_ABUSE_EXEMPTION`` cookie that
unlocks real results on that IP — which the fetch seam caches per proxy so one
solve amortizes across subsequent fetches (see ``fetch._exemption_jar``).

The actual vendor call goes through the shared, in-house solver seam
(:mod:`app.utils.captcha.solvers`) with ``enterprise=True`` + the page's
``data-s`` — this module just detects the wall, harvests via that seam egressing
through the render's own sticky proxy, injects the token, and submits.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from typing import Any

from app.utils.captcha import CaptchaConfig
from app.utils.captcha import solvers

logger = logging.getLogger(__name__)

_LOG = "[google_search][captcha]"

# The /sorry page embeds the widget sitekey and a dynamic `data-s` token that
# the Enterprise challenge binds to; both are mandatory in the solve request.
_SITEKEY_RE = re.compile(r'data-sitekey="([\w-]+)"')
_DATA_S_RE = re.compile(r'data-s="([^"]+)"')

# After submitting the solved /sorry form, Google 302s back to the SERP. We wait
# only for the results container to attach — NOT for full network idle. A
# rendered SERP fires telemetry/XHRs that keep the network busy long past the
# point results are present, so a `networkidle` wait here burned up to its full
# timeout on every solve for no benefit; the container's presence is the real
# "we're through the wall" signal.
_POST_SOLVE_WAIT_MS = 15000

# Process-wide kill switch tripped on unrecoverable solver errors (no balance /
# bad key). Persists across the per-fetch page_action instances of one run;
# nothing short of a restart fixes balance/key, so keep hammering off.
_latched = False


def solver_latched() -> bool:
    return _latched


def reset_solver_latch() -> None:
    """Clear the process latch (test seam / explicit re-enable)."""
    global _latched
    _latched = False


def _latch(reason: str) -> None:
    global _latched
    _latched = True
    logger.warning("%s solver latched OFF for this process: %s", _LOG, reason)


def on_sorry(page: Any) -> bool:
    """True when the render landed on Google's ``/sorry`` reCAPTCHA wall."""
    return "/sorry/" in (getattr(page, "url", "") or "")


# Set the token into the response textarea and submit the /sorry form. Google's
# /sorry form posts to /sorry/index and, on a valid token, 302s back to the
# `continue` URL (the SERP) while setting GOOGLE_ABUSE_EXEMPTION.
_INJECT_JS = r"""
(token) => {
  let ta = document.getElementById('g-recaptcha-response');
  if (!ta) {
    ta = document.createElement('textarea');
    ta.id = 'g-recaptcha-response';
    ta.name = 'g-recaptcha-response';
    ta.style.display = 'none';
    (document.forms[0] || document.body).appendChild(ta);
  }
  ta.value = token; ta.innerHTML = token;
  const form = ta.closest('form') || document.forms[0];
  if (form) { try { form.requestSubmit ? form.requestSubmit() : form.submit(); } catch (e) { form.submit(); } }
}
"""

# Organic-results containers; presence means the exemption unlocked the SERP.
_RESULTS_SEL = "#search, #rso, div.tF2Cxc"


async def solve_sorry(page: Any, proxy_url: str | None, cfg: CaptchaConfig) -> bool:
    """Solve the ``/sorry`` challenge on ``page`` and submit; return solved.

    Runs inside the async render. On success the page ends on the real SERP and
    the context holds ``GOOGLE_ABUSE_EXEMPTION`` (the caller caches it). On any
    failure returns ``False`` and leaves the page on ``/sorry`` so the fetch
    loop moves to the next IP.
    """
    if solver_latched():
        return False
    try:
        html = await page.content()
    except Exception:
        return False
    sk = _SITEKEY_RE.search(html)
    ds = _DATA_S_RE.search(html)
    if not sk or not ds:
        logger.warning("%s /sorry page missing sitekey/data-s; cannot solve", _LOG)
        return False

    page_url = getattr(page, "url", "") or ""
    try:
        user_agent = await page.evaluate("() => navigator.userAgent")
    except Exception:
        user_agent = None

    logger.info("%s solving Enterprise reCAPTCHA site=%s", _LOG, sk.group(1)[:12])
    _t0 = time.perf_counter()
    try:
        token = await asyncio.to_thread(
            solvers.solve,
            cfg,
            challenge_type="v2",
            sitekey=sk.group(1),
            page_url=page_url,
            proxy_url=proxy_url,
            user_agent=user_agent,
            enterprise=True,
            data_s=ds.group(1),
        )
    except solvers.SolverError as e:
        # Bad key / no balance / unsupported provider won't fix without a
        # restart — latch so we stop hammering (and stop paying) this process.
        _latch(repr(e))
        return False
    except Exception as e:  # never let a solver hiccup break the render
        logger.warning("%s solve error: %s", _LOG, e)
        return False
    if not token:
        return False

    harvest_ms = (time.perf_counter() - _t0) * 1000
    try:
        await page.evaluate(_INJECT_JS, token)
    except Exception as e:
        logger.warning("%s token injection failed: %s", _LOG, e)
        return False
    with contextlib.suppress(Exception):
        await page.wait_for_selector(_RESULTS_SEL, timeout=_POST_SOLVE_WAIT_MS)

    solved = not on_sorry(page)
    logger.info(
        "%s solve %s harvest_ms=%.0f total_ms=%.0f",
        _LOG,
        "OK" if solved else "did not clear wall",
        harvest_ms,
        (time.perf_counter() - _t0) * 1000,
    )
    return solved


async def exemption_cookies(page: Any) -> list[dict]:
    """Snapshot the context's google.com cookies (for the per-proxy jar)."""
    try:
        return await page.context.cookies("https://www.google.com")
    except Exception:
        return []
