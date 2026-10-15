"""The captcha solver's settings, from SCRAPING_CAPTCHA_*: off without a key, so nothing is paid by accident."""

from dataclasses import dataclass

from proprietary.scraping.config import Config

# Google's Enterprise /sorry wall measured 27-39 s on capsolver and up to 100 s
# on 2captcha; past this a solve is abandoned and the next IP tried.
SOLVE_TIMEOUT_SECONDS = 120
# What a reCAPTCHA v3 solve asks for; Web Crawl's challenges, not Google Search's.
V3_MIN_SCORE = 0.7
V3_ACTION = "verify"


@dataclass(frozen=True)
class CaptchaConfig:
    provider: str
    api_key: str | None
    timeout_s: int = SOLVE_TIMEOUT_SECONDS
    v3_min_score: float = V3_MIN_SCORE
    v3_action: str = V3_ACTION


def get_captcha_config() -> CaptchaConfig:
    return CaptchaConfig(
        provider=Config.CAPTCHA_PROVIDER, api_key=Config.CAPTCHA_API_KEY
    )


def captcha_enabled() -> bool:
    return bool(Config.CAPTCHA_API_KEY)
