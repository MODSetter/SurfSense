"""App-wide captcha-solver configuration (Apache-2.0, generic glue).

This package holds the **generic, vendor-agnostic** config resolution for
captcha solving (:class:`CaptchaConfig`) plus the in-house vendor API clients
(:mod:`app.utils.captcha.solvers`) — mirroring ``app/utils/proxy/`` (which stays
Apache-2.0 even though the crawler that consumes it is proprietary). The actual
bypass logic (challenge detection + token injection ``page_action``) lives in
the separately licensed ``app/proprietary/web_crawler/captcha.py`` and
``app/proprietary/platforms/google_search/captcha.py``.

``solvers.solve()`` dispatches on ``CAPTCHA_SOLVER_PROVIDER``; only 2captcha is
wired today, more vendors are added progressively. ``captcha_enabled()`` is the
cheap gate callers check before constructing anything (mirrors
``WebCrawlCreditService.billing_enabled()``).
"""

from app.utils.captcha.config import (
    CaptchaConfig,
    captcha_enabled,
    get_captcha_config,
)

__all__ = ["CaptchaConfig", "captcha_enabled", "get_captcha_config"]
