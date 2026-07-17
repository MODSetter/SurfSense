"""Cross-country exit rotation for warm-session scrapers.

Some targets (Reddit's ``loid``, TikTok's ``ttwid``) silently withhold their
anonymous session cookie from the provider's *default worldwide* pool but hand
it out freely on **country-pinned** exits (proven live: a bare-pool homepage
hit returns 200 with an empty cookie jar, while a us/gb/de/nl-pinned hit mints
the cookie every time). A warm-on-block flow that only re-draws from the same
worldwide pool therefore burns every rotation on cookie-less IPs and fails.

Walking a spread of country pools instead lets the flow escape a wholly-blocked
pool. The provider's configured country leads (so an operator's choice is
honoured first); the fallbacks are large, reliable residential pools. Non-geo
providers (e.g. the custom single-URL provider) ignore the country and re-draw
their one URL, so this is a harmless no-op there.
"""

from __future__ import annotations

from app.utils.proxy.registry import get_active_provider

# Walk order after the configured country. Ordered by pool size / reliability.
FALLBACK_COUNTRIES = ("us", "gb", "de", "ca", "nl", "fr")


def rotation_countries() -> tuple[str, ...]:
    """Ordered, de-duplicated exit countries with the configured one leading."""
    lead = get_active_provider().get_location()
    return tuple(dict.fromkeys(c for c in (lead, *FALLBACK_COUNTRIES) if c))


def country_for_rotation(n: int) -> str:
    """Exit country for rotation index ``n`` (cycles the list, wrapping around)."""
    countries = rotation_countries()
    return countries[n % len(countries)]
