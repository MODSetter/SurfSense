"""Captcha detection and token injection for the stealth tier's ``page_action``.

The solve egresses through the crawl's own proxy, since tokens are IP-bound.
Scrapling swallows a ``page_action``'s exceptions and return value, so attempts
and success reach the crawler through a caller-owned ``state`` dict. An
unrecoverable solver error (no balance, bad key) latches solving off for the
process: hammering a solver out of balance can get the IP banned.
"""

import asyncio
import contextlib
import logging
import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

from proprietary.scraping.captcha import CaptchaConfig, solvers

logger = logging.getLogger(__name__)

_CAPTCHA_LOG = "[webcrawler][captcha]"

# Paid solves per URL, across the proxy-retry re-runs that share one ``state``.
MAX_ATTEMPTS_PER_URL = int(os.getenv("CAPTCHA_MAX_ATTEMPTS_PER_URL", "1"))
# "v3" also looks for a widgetless reCAPTCHA v3 sitekey on the api.js script.
CHALLENGE_TYPE_DEFAULT = os.getenv("CAPTCHA_TYPE_DEFAULT", "v2")

_solver_latched = False


def reset_solver_latch() -> None:
    """Clear the process solver latch (test seam / explicit re-enable)."""
    global _solver_latched
    _solver_latched = False


def solver_latched() -> bool:
    return _solver_latched


def _latch_solver(reason: str) -> None:
    global _solver_latched
    _solver_latched = True
    logger.warning("%s solver latched OFF for this process: %s", _CAPTCHA_LOG, reason)


# --- detection -------------------------------------------------------------

# (challenge_type, css_selector_for_widget). Order = detection priority.
_WIDGET_SELECTORS = (
    ("v2", ".g-recaptcha[data-sitekey]"),
    ("hcaptcha", ".h-captcha[data-sitekey]"),
)
_IFRAME_PATTERNS = (
    ("v2", re.compile(r"google\.com/recaptcha", re.I)),
    ("hcaptcha", re.compile(r"hcaptcha\.com", re.I)),
)
_SITEKEY_IN_SRC = re.compile(r"[?&]k=([\w-]+)")
_RENDER_SITEKEY = re.compile(r"render=([\w-]+)")


async def detect_challenge(
    page: Any, type_default: str = CHALLENGE_TYPE_DEFAULT
) -> tuple[str, str] | None:
    """``(challenge_type, sitekey)`` of a solvable challenge on ``page``, else ``None``.

    ``challenge_type`` is ``v2``, ``v3`` or ``hcaptcha``. A DOM access that
    raises reads as no challenge rather than aborting the fetch.
    """
    try:
        for ctype, selector in _WIDGET_SELECTORS:
            el = await page.query_selector(selector)
            if el is not None:
                sitekey = await el.get_attribute("data-sitekey")
                if sitekey:
                    return ctype, sitekey

        # The widget rendered in an iframe whose src carries the sitekey as ?k=.
        for frame_el in await page.query_selector_all("iframe[src]") or []:
            src = await frame_el.get_attribute("src") or ""
            for ctype, pat in _IFRAME_PATTERNS:
                if pat.search(src):
                    m = _SITEKEY_IN_SRC.search(src)
                    if m:
                        return ctype, m.group(1)

        # reCAPTCHA v3 has no widget; its sitekey rides api.js's ?render=<key>.
        if type_default == "v3":
            for script_el in await page.query_selector_all("script[src]") or []:
                src = await script_el.get_attribute("src") or ""
                if "recaptcha" in src.lower():
                    m = _RENDER_SITEKEY.search(src)
                    if m and m.group(1) != "explicit":
                        return "v3", m.group(1)
    except Exception as exc:
        logger.debug(
            "%s detection error (treated as no challenge): %s", _CAPTCHA_LOG, exc
        )
    return None


# --- harvest ---------------------------------------------------------------


async def _harvest_token(
    cfg: CaptchaConfig,
    challenge_type: str,
    sitekey: str,
    page_url: str,
    proxy: str | None,
    user_agent: str | None,
) -> str | None:
    """A token from the solver, or ``None``; raises on solver errors so the caller can latch."""
    return await solvers.solve(
        cfg,
        challenge_type=challenge_type,
        sitekey=sitekey,
        page_url=page_url,
        proxy_url=proxy,
        user_agent=user_agent,
    )


# --- injection -------------------------------------------------------------

# Sets the token into the response textarea(s), fires the widget's JS callbacks,
# and submits the closest form. Success is judged by the crawler's extraction.
_INJECT_JS = r"""
(args) => {
  const { token, ctype } = args;
  const names = ctype === 'hcaptcha'
    ? ['h-captcha-response', 'g-recaptcha-response']
    : ['g-recaptcha-response'];
  for (const name of names) {
    let ta = document.querySelector('textarea[name="' + name + '"]')
           || document.getElementById(name);
    if (!ta) {
      ta = document.createElement('textarea');
      ta.name = name; ta.id = name;
      ta.style.display = 'none';
      document.body.appendChild(ta);
    }
    ta.value = token; ta.innerHTML = token;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
  }
  // Fire grecaptcha client callbacks when present (v2 invisible / explicit).
  try {
    const cfg = window.___grecaptcha_cfg;
    if (cfg && cfg.clients) {
      for (const id in cfg.clients) {
        const client = cfg.clients[id];
        for (const k in client) {
          const o = client[k];
          if (o && typeof o === 'object') {
            for (const kk in o) {
              const cb = o[kk];
              if (cb && cb.callback && typeof cb.callback === 'function') {
                try { cb.callback(token); } catch (e) {}
              }
            }
          }
        }
      }
    }
  } catch (e) {}
  // Submit the form containing the response field, if any.
  const field = document.querySelector('textarea[name="g-recaptcha-response"], textarea[name="h-captcha-response"]');
  const form = field ? field.closest('form') : document.querySelector('form');
  if (form) { try { form.requestSubmit ? form.requestSubmit() : form.submit(); } catch (e) {} }
}
"""


async def _inject_and_submit(page: Any, challenge_type: str, token: str) -> None:
    try:
        await page.evaluate(_INJECT_JS, {"token": token, "ctype": challenge_type})
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception as exc:
        logger.warning("%s injection error: %s", _CAPTCHA_LOG, exc)


# --- factory ---------------------------------------------------------------


def build_captcha_page_action(
    state: dict[str, Any],
    proxy_url: str | None,
    cfg: CaptchaConfig,
    *,
    max_attempts: int = MAX_ATTEMPTS_PER_URL,
    type_default: str = CHALLENGE_TYPE_DEFAULT,
) -> Callable[[Any], Awaitable[Any]] | None:
    """The async ``page_action`` for the stealth fetch, or ``None`` when solving is off or latched.

    ``state`` gets ``attempts`` and ``solved``, read back after the fetch.
    """
    if not cfg.api_key or solver_latched():
        return None

    async def page_action(page: Any) -> Any:
        if state.get("attempts", 0) >= max_attempts:
            return page
        if solver_latched():
            return page

        detected = await detect_challenge(page, type_default)
        if detected is None:
            return page
        challenge_type, sitekey = detected

        page_url = getattr(page, "url", "") or ""
        try:
            user_agent = await page.evaluate("() => navigator.userAgent")
        except Exception:
            user_agent = None

        # An attempt the moment the paid solver is called.
        state["attempts"] = state.get("attempts", 0) + 1
        logger.info(
            "%s solving type=%s site=%s attempt=%d",
            _CAPTCHA_LOG,
            challenge_type,
            sitekey[:12],
            state["attempts"],
        )

        try:
            async with asyncio.timeout(cfg.timeout_s):
                token = await _harvest_token(
                    cfg, challenge_type, sitekey, page_url, proxy_url, user_agent
                )
        except TimeoutError:
            logger.warning("%s solve timed out after %ss", _CAPTCHA_LOG, cfg.timeout_s)
            return page
        except Exception as exc:
            if _is_unrecoverable(exc):
                _latch_solver(repr(exc))
            else:
                logger.warning("%s solve error: %s", _CAPTCHA_LOG, exc)
            return page

        if not token:
            return page

        await _inject_and_submit(page, challenge_type, token)
        state["solved"] = True
        logger.info(
            "%s solved type=%s site=%s", _CAPTCHA_LOG, challenge_type, sitekey[:12]
        )
        return page

    return page_action


def _is_unrecoverable(exc: Exception) -> bool:
    """Solver errors that latch solving off: the typed ``SolverError``s, or a no-balance/bad-key shape by name."""
    if isinstance(exc, solvers.SolverError):
        return True
    name = type(exc).__name__.lower()
    return any(
        k in name for k in ("balance", "apikey", "auth", "unsupported", "wronguser")
    )
