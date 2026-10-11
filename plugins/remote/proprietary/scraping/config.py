"""Settings every scraper plugin shares, from SCRAPING_* environment variables.

Secrets come from Key Vault into the environment; none reaches the app.
"""

import os


class Config:
    """Read once at import, as the backend's settings were."""

    # The proxy vendor: `dataimpulse` or `nodemaven`. Unset, scrapes go direct.
    PROXY_PROVIDER = os.getenv("SCRAPING_PROXY_PROVIDER")
    # The vendor's endpoint, http://user:pass@host:port.  # pragma: allowlist secret
    PROXY_URL = os.getenv("SCRAPING_PROXY_URL")
