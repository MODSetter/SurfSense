"""Block classifier — labels a fetched page so the ladder can learn (Phase 3e).

Pure, additive, status + body-marker based. It attaches
:class:`~app.proprietary.web_crawler.connector.CrawlOutcome.block_type` for
telemetry / future escalation routing (per-domain memory, `03d` captcha routing)
and **never** changes *when* a crawl is ``SUCCESS`` — `03c` bills on
``status == SUCCESS``, so this stays read-only metadata.

Markers mirror the proven set in the Camoufox-based FlareSolverr alternative
``references/trawl-dev/packages/tiers/src/detect.ts`` (plus DataDome/Kasada for
our enterprise targets). Regexes are compiled once at import (hot-path hygiene).
"""

import re
from enum import Enum


class BlockType(str, Enum):
    """Coarse label for what a fetched page represents."""

    OK = "ok"  # usable content, no challenge detected
    CLOUDFLARE = "cloudflare"  # CF interstitial / Turnstile / DDoS-Guard
    CAPTCHA_RECAPTCHA = "captcha_recaptcha"
    CAPTCHA_HCAPTCHA = "captcha_hcaptcha"
    DATADOME = "datadome"
    KASADA = "kasada"
    RATE_LIMITED = "rate_limited"
    EMPTY = "empty"  # fetched but no HTML body
    UNKNOWN = "unknown"  # blocking-ish status with no recognized marker


# --- compiled marker patterns (hoisted; see Vercel rule 7.9) ---
_CLOUDFLARE = re.compile(
    r"just a moment"
    r"|checking your browser"
    r"|enable javascript and cookies to continue"
    r"|verify you are human"
    r"|cf-mitigated"
    r"|id=\"(?:cf-)?challenge-running\""
    r"|id=\"turnstile-wrapper\""
    r"|ddos-guard",
    re.IGNORECASE,
)
_TURNSTILE = re.compile(
    r"class=\"cf-turnstile\""
    r"|challenges\.cloudflare\.com/turnstile"
    r"|cdn-cgi/challenge-platform[^\"']*turnstile",
    re.IGNORECASE,
)
_HCAPTCHA = re.compile(r"class=\"h-captcha\"|hcaptcha\.com/1/api", re.IGNORECASE)
_RECAPTCHA = re.compile(
    r"class=\"g-recaptcha\"|google\.com/recaptcha|recaptcha\.net/recaptcha",
    re.IGNORECASE,
)
_DATADOME = re.compile(r"datadome|geo\.captcha-delivery\.com", re.IGNORECASE)
_KASADA = re.compile(r"kpsdk|x-kpsdk|kasada", re.IGNORECASE)

# Statuses some CDNs use as a bot-gate before the real response (detect.ts:isBlocked).
_BOT_GATE_STATUSES = frozenset({202, 403})


def classify_block(status: int | None, html: str | None) -> BlockType:
    """Label a fetched page from its HTTP status and HTML body.

    Precedence: explicit rate-limit status, then specific anti-bot/captcha body
    markers, then a generic bot-gate status with no marker, else ``OK`` (or
    ``EMPTY`` when there is no body). Marker checks run before the generic
    bot-gate so a ``403`` Cloudflare challenge is labeled ``CLOUDFLARE``, not
    ``UNKNOWN``.
    """
    if status == 429:
        return BlockType.RATE_LIMITED

    if not html or not html.strip():
        # No body: distinguish a blocking-ish status from a genuinely empty 200.
        if status in _BOT_GATE_STATUSES:
            return BlockType.UNKNOWN
        return BlockType.EMPTY

    if _CLOUDFLARE.search(html) or _TURNSTILE.search(html):
        return BlockType.CLOUDFLARE
    if _DATADOME.search(html):
        return BlockType.DATADOME
    if _KASADA.search(html):
        return BlockType.KASADA
    if _HCAPTCHA.search(html):
        return BlockType.CAPTCHA_HCAPTCHA
    if _RECAPTCHA.search(html):
        return BlockType.CAPTCHA_RECAPTCHA

    if status in _BOT_GATE_STATUSES:
        return BlockType.UNKNOWN

    return BlockType.OK
