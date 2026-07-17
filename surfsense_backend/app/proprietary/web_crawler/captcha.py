# SurfSense proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""Captcha detection + token-injection ``page_action`` (Phase 3d).

This is the **bypass logic** (hence proprietary); the generic, vendor-agnostic
config and the vendor API clients live in the Apache-2.0 ``app/utils/captcha/``
package (:mod:`app.utils.captcha.solvers`). We only detect the challenge,
harvest a token through that seam egressing from **the crawl's own proxy IP**
(token IP-binding), inject it, and submit.

Why a closure cell: Scrapling runs ``page_action`` after navigation but
**swallows its exceptions and discards its return value** (see
``references/Scrapling`` engine ``_stealth.py``). So the only way to surface
"did we solve / how many attempts" back to the crawler (for per-attempt billing
and the retry cap) is to mutate a caller-owned ``state`` dict.

Why a process latch: the solver README warns that hammering it while out of
balance can get the IP **temporarily banned**, so ``ErrNoBalance`` /
``ErrWrongAPIKey`` latch solving OFF for the rest of the process (config/balance
won't change without a restart). ``reset_solver_latch()`` clears it for tests.
"""

import contextlib
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from app.utils.captcha import CaptchaConfig

logger = logging.getLogger(__name__)

_CAPTCHA_LOG = "[webcrawler][captcha]"

# Process-wide kill switch tripped on unrecoverable solver errors (no balance /
# bad key). Module-level by design: it must persist across the per-URL
# ``page_action`` instances created during one crawl run.
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


def detect_challenge(page: Any, cfg: CaptchaConfig) -> tuple[str, str] | None:
    """Return ``(challenge_type, sitekey)`` if a solvable challenge is present.

    ``challenge_type`` is one of ``v2`` / ``v3`` / ``hcaptcha``. Returns
    ``None`` when nothing solvable is found (the crawler then proceeds to
    ``wait_selector`` / extraction unchanged). Detection is defensive: any DOM
    access raising is treated as "not found" rather than aborting the fetch.
    """
    try:
        for ctype, selector in _WIDGET_SELECTORS:
            el = page.query_selector(selector)
            if el is not None:
                sitekey = el.get_attribute("data-sitekey")
                if sitekey:
                    return ctype, sitekey

        # Iframe fallback: widget rendered inside an iframe whose src carries
        # the sitekey as ``?k=...``.
        for frame_el in page.query_selector_all("iframe[src]") or []:
            src = frame_el.get_attribute("src") or ""
            for ctype, pat in _IFRAME_PATTERNS:
                if pat.search(src):
                    m = _SITEKEY_IN_SRC.search(src)
                    if m:
                        return ctype, m.group(1)

        # reCAPTCHA v3: no widget; sitekey rides the api.js ``?render=<key>``.
        if cfg.captcha_type_default == "v3":
            for script_el in page.query_selector_all("script[src]") or []:
                src = script_el.get_attribute("src") or ""
                if "recaptcha" in src.lower():
                    m = _RENDER_SITEKEY.search(src)
                    if m and m.group(1) != "explicit":
                        return "v3", m.group(1)
    except Exception as exc:
        logger.debug(
            "%s detection error (treated as no challenge): %s", _CAPTCHA_LOG, exc
        )
    return None


# --- proxy / harvest -------------------------------------------------------


def _harvest_token(
    cfg: CaptchaConfig,
    challenge_type: str,
    sitekey: str,
    page_url: str,
    proxy: str | None,
    user_agent: str | None,
) -> str | None:
    """Harvest a token from the in-house solver seam. Raises on solver errors so
    the caller can latch on the unrecoverable ones; returns ``None`` on an empty
    token. ``proxy`` is a raw ``http://user:pass@host:port`` URL (the seam
    reformats it per vendor).
    """
    from app.utils.captcha import solvers

    return solvers.solve(
        cfg,
        challenge_type=challenge_type,
        sitekey=sitekey,
        page_url=page_url,
        proxy_url=proxy,
        user_agent=user_agent,
    )


# --- injection -------------------------------------------------------------

# Sets the response token into the right textarea(s) and fires the JS callbacks
# registered by the widget, then submits the closest form. Best-effort: returns
# nothing; success is judged by the crawler's post-fetch extraction.
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


def _inject_and_submit(page: Any, challenge_type: str, token: str) -> None:
    try:
        page.evaluate(_INJECT_JS, {"token": token, "ctype": challenge_type})
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=15000)
    except Exception as exc:
        logger.warning("%s injection error: %s", _CAPTCHA_LOG, exc)


# --- factory ---------------------------------------------------------------


def build_captcha_page_action(
    state: dict[str, Any],
    proxy_url: str | None,
    cfg: CaptchaConfig,
) -> Callable[[Any], Any] | None:
    """Build the sync ``page_action`` for ``StealthyFetcher.fetch``.

    ``state`` is mutated in place: ``attempts`` (int) and ``solved`` (bool). The
    crawler reads it back after the fetch to bill per attempt and enforce the
    per-URL cap. Returns ``None`` when solving is disabled/latched so the caller
    can skip wiring it entirely (keeping the stealth tier unchanged).
    """
    if not cfg.enabled or solver_latched():
        return None

    # Raw URL; the solver seam reformats it per vendor and binds the token to
    # this exit IP.
    captcha_proxy = proxy_url

    def page_action(page: Any) -> Any:
        # Hard cap: never exceed the per-URL budget even across proxy-retry
        # re-runs that share this ``state``.
        if state.get("attempts", 0) >= cfg.max_attempts_per_url:
            return page
        if solver_latched():
            return page

        detected = detect_challenge(page, cfg)
        if detected is None:
            return page  # nothing to solve; let extraction proceed
        challenge_type, sitekey = detected

        page_url = getattr(page, "url", "") or ""
        try:
            user_agent = page.evaluate("() => navigator.userAgent")
        except Exception:
            user_agent = None

        # This counts as an attempt the moment we call the (paid) solver.
        state["attempts"] = state.get("attempts", 0) + 1
        logger.info(
            "%s solving type=%s site=%s attempt=%d",
            _CAPTCHA_LOG,
            challenge_type,
            sitekey[:12],
            state["attempts"],
        )

        # Run the (blocking) solver in a worker so the timeout can actually
        # ABANDON a slow solve. NOTE: do NOT use ``with ThreadPoolExecutor`` —
        # its ``__exit__`` joins the worker (``wait=True``), which would block
        # for the full solve and defeat the timeout. Shut down non-blocking.
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            _harvest_token,
            cfg,
            challenge_type,
            sitekey,
            page_url,
            captcha_proxy,
            user_agent,
        )
        try:
            token = future.result(timeout=cfg.timeout_s)
        except FuturesTimeout:
            logger.warning("%s solve timed out after %ss", _CAPTCHA_LOG, cfg.timeout_s)
            return page
        except Exception as exc:
            if _is_unrecoverable(exc):
                _latch_solver(repr(exc))
            else:
                logger.warning("%s solve error: %s", _CAPTCHA_LOG, exc)
            return page
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if not token:
            return page

        _inject_and_submit(page, challenge_type, token)
        state["solved"] = True
        logger.info(
            "%s solved type=%s site=%s", _CAPTCHA_LOG, challenge_type, sitekey[:12]
        )
        return page

    return page_action


def _is_unrecoverable(exc: Exception) -> bool:
    """True for solver errors that must latch solving off.

    Covers the in-house seam's typed errors (``SolverBalanceError`` /
    ``SolverAuthError`` / ``SolverUnsupportedError``) plus legacy/no-balance shapes.
    Matched by class name so no solver module must be imported here.
    """
    name = type(exc).__name__.lower()
    return any(
        k in name for k in ("balance", "apikey", "auth", "unsupported", "wronguser")
    )
