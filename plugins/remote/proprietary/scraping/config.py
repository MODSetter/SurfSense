"""Settings every scraper plugin shares, from SCRAPING_* environment variables.

Secrets come from Key Vault into the environment; none reaches the app.
"""

import os


class Config:
    """Read once at import, as the backend's settings were."""

    # Which provider reads the proxy URLs: `custom`, `dataimpulse` or `nodemaven`.
    PROXY_PROVIDER = os.getenv("SCRAPING_PROXY_PROVIDER", "custom")
    # One full http://user:pass@host:port endpoint. Unset, scrapes go direct.  # pragma: allowlist secret
    PROXY_URL = os.getenv("SCRAPING_PROXY_URL")
    # Comma-separated endpoints the `custom` provider rotates through.
    PROXY_URLS = os.getenv("SCRAPING_PROXY_URLS")
