"""App-wide captcha-solver configuration (Apache-2.0, generic glue).

This package holds only the **generic, vendor-agnostic** config resolution for
captcha solving — mirroring ``app/utils/proxy/`` (which stays Apache-2.0 even
though the crawler that consumes it is proprietary). The actual bypass logic
(challenge detection + token injection ``page_action``) lives in the separately
licensed ``app/proprietary/web_crawler/captcha.py``.

``captchatools`` is itself the multi-vendor registry (capmonster / 2captcha /
anticaptcha / capsolver / captchaai), so there is no provider hierarchy here —
just one env-driven :class:`CaptchaConfig` and a cheap ``captcha_enabled()``
gate callers check before constructing anything (mirrors
``WebCrawlCreditService.billing_enabled()``).
"""

from app.utils.captcha.config import (
    CaptchaConfig,
    captcha_enabled,
    get_captcha_config,
)

__all__ = ["CaptchaConfig", "captcha_enabled", "get_captcha_config"]
