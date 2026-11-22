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

    # Requests in flight through scraping/http.py at once, across every plugin: what
    # the host lets the proxy plan see. A request over the limit waits its turn.
    MAX_HTTP = int(os.getenv("SCRAPING_MAX_HTTP", "48"))
    # Keep-alive sessions kept warm between tool calls by plugins that ask for it
    # (scraping/sessions.py). 0 turns that reuse off everywhere.
    MAX_IDLE_SESSIONS = int(os.getenv("SCRAPING_MAX_IDLE_SESSIONS", "16"))
    # 0 turns hedging off: scraping/concurrency.hedged then runs only the first attempt.
    HEDGE = os.getenv("SCRAPING_HEDGE", "1") != "0"
