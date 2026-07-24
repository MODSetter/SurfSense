"""Env-resolved captcha-solver config (one app-wide config; no per-connector).

Resolved from :data:`app.config.config` only, mirroring ``03b``'s single
``PROXY_PROVIDER`` model. Off by default: ``captcha_enabled()`` is ``False``
unless both ``CAPTCHA_SOLVING_ENABLED=TRUE`` and an API key are present, so a
misconfigured deployment (flag on, key missing) never attempts a paid solve.
"""

from dataclasses import dataclass

from app.config import config


@dataclass(frozen=True)
class CaptchaConfig:
    """Immutable snapshot of the captcha-solver settings for one crawl."""

    enabled: bool
    solving_site: str
    api_key: str | None
    max_attempts_per_url: int
    timeout_s: int
    captcha_type_default: str
    v3_min_score: float
    v3_action: str


def get_captcha_config() -> CaptchaConfig:
    """Build a :class:`CaptchaConfig` from the current process config/env."""
    api_key = config.CAPTCHA_SOLVER_API_KEY
    flag_on = config.CAPTCHA_SOLVING_ENABLED
    return CaptchaConfig(
        # Effective-enabled requires a key too: a flag with no key would only
        # produce ``ErrWrongAPIKey`` per attempt (and still risk an IP ban from
        # the solver), so treat key-less config as disabled.
        enabled=bool(flag_on and api_key),
        solving_site=config.CAPTCHA_SOLVER_PROVIDER,
        api_key=api_key,
        max_attempts_per_url=config.CAPTCHA_MAX_ATTEMPTS_PER_URL,
        timeout_s=config.CAPTCHA_SOLVE_TIMEOUT_S,
        captcha_type_default=config.CAPTCHA_TYPE_DEFAULT,
        v3_min_score=config.CAPTCHA_V3_MIN_SCORE,
        v3_action=config.CAPTCHA_V3_ACTION,
    )


def captcha_enabled() -> bool:
    """Cheap gate: is captcha solving effectively configured (flag + key)?

    Callers check this before building the ``page_action`` or capturing the
    crawl's proxy endpoint for the solver, so the stealth tier stays unchanged
    when solving is off.
    """
    return bool(config.CAPTCHA_SOLVING_ENABLED and config.CAPTCHA_SOLVER_API_KEY)
