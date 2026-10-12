"""Settings every scraper plugin shares, from SCRAPING_* environment variables.

Secrets come from the deployment's secret store into the environment; none reaches the app.
"""

import os


class Config:
    """Read once at import, as the backend's settings were."""

    # The proxy vendor: `dataimpulse` or `nodemaven`. Unset, scrapes go direct.
    PROXY_PROVIDER = os.getenv("SCRAPING_PROXY_PROVIDER")
    # The vendor's endpoint, http://user:pass@host:port.  # pragma: allowlist secret
    PROXY_URL = os.getenv("SCRAPING_PROXY_URL")
    # The captcha solver, `capsolver` or `2captcha`, and its key. No key, no solves.
    CAPTCHA_PROVIDER = os.getenv("SCRAPING_CAPTCHA_PROVIDER", "capsolver")
    CAPTCHA_API_KEY = os.getenv("SCRAPING_CAPTCHA_API_KEY")
