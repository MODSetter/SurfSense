# SurfSense proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""Stealth-hardening config + the centralized per-tier kwargs builder (Phase 3e).

This is **bypass-specific tuning** (hence proprietary): it decides the
anti-detection lever set the StealthyFetcher tier runs with (WebRTC/canvas/DNS
handling, organic-referer, and proxy-geo-coherent ``locale``/``timezone_id``).
It is the **single source of truth** that turns config -> ``StealthyFetcher``
keyword arguments, imported by both the crawler (``connector.py``) and the 03f
manual harness, so the scorecard grades the exact browser we ship (no
test-vs-prod drift).

The generic, vendor-agnostic block *classifier* (passive telemetry, public
markers) stays Apache-2.0 in ``app/utils/crawl/``. The further bypass logic
(WebGL spoof JS, humanize choreography) is deferred to later 03e slices and will
also live here.

Defaults preserve today's behavior and add **no crawl-speed regression**:
``dns_over_https`` (the only lever with a latency cost) is off unless explicitly
enabled, and geoip resolution is a pure in-process dict lookup (no exit-IP call).
"""

from dataclasses import dataclass
from typing import Any

from app.config import config

# Coarse region -> (locale, IANA timezone) map. Country granularity only: per the
# 03e "Geoip accuracy" risk, wrong-but-coherent beats a default mismatch and
# per-city precision isn't worth it. Keyed by ISO-3166 alpha-2; common full names
# are aliased below. Unknown/empty => (None, None) => leave Scrapling's default.
_REGION_TO_LOCALE_TZ: dict[str, tuple[str, str]] = {
    "us": ("en-US", "America/New_York"),
    "ca": ("en-CA", "America/Toronto"),
    "gb": ("en-GB", "Europe/London"),
    "ie": ("en-IE", "Europe/Dublin"),
    "au": ("en-AU", "Australia/Sydney"),
    "nz": ("en-NZ", "Pacific/Auckland"),
    "de": ("de-DE", "Europe/Berlin"),
    "fr": ("fr-FR", "Europe/Paris"),
    "es": ("es-ES", "Europe/Madrid"),
    "it": ("it-IT", "Europe/Rome"),
    "nl": ("nl-NL", "Europe/Amsterdam"),
    "be": ("nl-BE", "Europe/Brussels"),
    "ch": ("de-CH", "Europe/Zurich"),
    "at": ("de-AT", "Europe/Vienna"),
    "se": ("sv-SE", "Europe/Stockholm"),
    "no": ("nb-NO", "Europe/Oslo"),
    "dk": ("da-DK", "Europe/Copenhagen"),
    "fi": ("fi-FI", "Europe/Helsinki"),
    "pl": ("pl-PL", "Europe/Warsaw"),
    "pt": ("pt-PT", "Europe/Lisbon"),
    "ru": ("ru-RU", "Europe/Moscow"),
    "ua": ("uk-UA", "Europe/Kyiv"),
    "tr": ("tr-TR", "Europe/Istanbul"),
    "in": ("en-IN", "Asia/Kolkata"),
    "jp": ("ja-JP", "Asia/Tokyo"),
    "kr": ("ko-KR", "Asia/Seoul"),
    "cn": ("zh-CN", "Asia/Shanghai"),
    "hk": ("zh-HK", "Asia/Hong_Kong"),
    "tw": ("zh-TW", "Asia/Taipei"),
    "sg": ("en-SG", "Asia/Singapore"),
    "id": ("id-ID", "Asia/Jakarta"),
    "ph": ("en-PH", "Asia/Manila"),
    "th": ("th-TH", "Asia/Bangkok"),
    "vn": ("vi-VN", "Asia/Ho_Chi_Minh"),
    "ae": ("ar-AE", "Asia/Dubai"),
    "il": ("he-IL", "Asia/Jerusalem"),
    "za": ("en-ZA", "Africa/Johannesburg"),
    "br": ("pt-BR", "America/Sao_Paulo"),
    "mx": ("es-MX", "America/Mexico_City"),
    "ar": ("es-AR", "America/Argentina/Buenos_Aires"),
    "cl": ("es-CL", "America/Santiago"),
}

# Full-name / synonym aliases -> alpha-2 key above.
_REGION_ALIASES: dict[str, str] = {
    "usa": "us",
    "united states": "us",
    "united states of america": "us",
    "america": "us",
    "uk": "gb",
    "united kingdom": "gb",
    "great britain": "gb",
    "england": "gb",
    "canada": "ca",
    "australia": "au",
    "germany": "de",
    "deutschland": "de",
    "france": "fr",
    "spain": "es",
    "italy": "it",
    "netherlands": "nl",
    "holland": "nl",
    "sweden": "se",
    "norway": "no",
    "denmark": "dk",
    "finland": "fi",
    "poland": "pl",
    "portugal": "pt",
    "russia": "ru",
    "ukraine": "ua",
    "turkey": "tr",
    "india": "in",
    "japan": "jp",
    "korea": "kr",
    "south korea": "kr",
    "china": "cn",
    "hong kong": "hk",
    "taiwan": "tw",
    "singapore": "sg",
    "indonesia": "id",
    "philippines": "ph",
    "thailand": "th",
    "vietnam": "vn",
    "israel": "il",
    "south africa": "za",
    "brazil": "br",
    "brasil": "br",
    "mexico": "mx",
    "argentina": "ar",
    "chile": "cl",
}


def location_to_locale_timezone(
    location: str | None,
) -> tuple[str | None, str | None]:
    """Map a free-form proxy region string -> (locale, timezone_id).

    ``location`` is the vendor-specific ``RESIDENTIAL_PROXY_LOCATION`` value
    (``03b``). Best-effort: matches an ISO-3166 alpha-2 code (e.g. ``"us"``) or a
    common country name (e.g. ``"Germany"``); only the leading token is honored,
    so vendor strings like ``"us:nyc"`` or ``"de region"`` still resolve. Returns
    ``(None, None)`` for empty/unknown input (caller then leaves the browser
    default).
    """
    if not location:
        return (None, None)

    normalized = location.strip().lower()
    if not normalized:
        return (None, None)

    # Direct alpha-2 hit.
    if normalized in _REGION_TO_LOCALE_TZ:
        return _REGION_TO_LOCALE_TZ[normalized]

    # Full-name / synonym hit.
    if normalized in _REGION_ALIASES:
        return _REGION_TO_LOCALE_TZ[_REGION_ALIASES[normalized]]

    # Leading token (handles "us:nyc", "de-rotating", "united states (east)").
    head = normalized.replace("-", " ").replace("_", " ").replace(":", " ").split()
    if head:
        token = head[0]
        if token in _REGION_TO_LOCALE_TZ:
            return _REGION_TO_LOCALE_TZ[token]
        if token in _REGION_ALIASES:
            return _REGION_TO_LOCALE_TZ[_REGION_ALIASES[token]]

    return (None, None)


@dataclass(frozen=True)
class StealthConfig:
    """Immutable snapshot of the Phase 3e Slice-A stealth levers for one crawl."""

    geoip_match_enabled: bool
    proxy_location: str
    block_webrtc: bool
    hide_canvas: bool
    google_search: bool
    dns_over_https: bool


def get_stealth_config() -> StealthConfig:
    """Build a :class:`StealthConfig` from the current process config/env."""
    return StealthConfig(
        geoip_match_enabled=config.CRAWL_GEOIP_MATCH_ENABLED,
        proxy_location=config.RESIDENTIAL_PROXY_LOCATION or "",
        block_webrtc=config.CRAWL_BLOCK_WEBRTC,
        hide_canvas=config.CRAWL_HIDE_CANVAS,
        google_search=config.CRAWL_GOOGLE_SEARCH_REFERER,
        dns_over_https=config.CRAWL_DNS_OVER_HTTPS,
    )


def build_stealthy_kwargs(cfg: StealthConfig) -> dict[str, Any]:
    """Return the config-derived ``StealthyFetcher.fetch`` keyword arguments.

    Only the Slice-A stealth levers are returned; the caller merges these into
    the tier's own kwargs (``headless``/``network_idle``/``block_ads``/
    ``solve_cloudflare``/``proxy``/captcha ``page_action``), which never collide
    with the keys here. ``locale``/``timezone_id`` are added only when geoip
    matching is enabled *and* the proxy region resolves — otherwise the browser
    keeps its system default.
    """
    kwargs: dict[str, Any] = {
        "block_webrtc": cfg.block_webrtc,
        "hide_canvas": cfg.hide_canvas,
        "google_search": cfg.google_search,
        "dns_over_https": cfg.dns_over_https,
    }

    if cfg.geoip_match_enabled:
        locale, timezone_id = location_to_locale_timezone(cfg.proxy_location)
        if locale:
            kwargs["locale"] = locale
        if timezone_id:
            kwargs["timezone_id"] = timezone_id

    return kwargs
