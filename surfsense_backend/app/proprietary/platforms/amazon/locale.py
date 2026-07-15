"""Marketplace locale helpers for Amazon fetch routing.

Only proxy countries verified against the configured DataImpulse plan are mapped
here. Unmapped marketplaces fall back to the default proxy exit.
"""

_MARKETPLACE_COUNTRY = {
    "com": "us",
    "co.uk": "gb",
    "de": "de",
    "fr": "fr",
    "it": "it",
    "es": "es",
}

_MARKETPLACE_LANGUAGE = {
    "com": "en-US",
    "co.uk": "en-GB",
    "de": "de-DE",
    "fr": "fr-FR",
    "it": "it-IT",
    "es": "es-ES",
}


def proxy_country_for(marketplace: str | None) -> str | None:
    """Return a confirmed proxy exit country for one Amazon marketplace."""
    return _MARKETPLACE_COUNTRY.get((marketplace or "").lower())


def accept_language_for(marketplace: str | None) -> str:
    """Return the browser language header that matches the marketplace UI."""
    return _MARKETPLACE_LANGUAGE.get((marketplace or "").lower(), "en-US")
