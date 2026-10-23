"""The license portal at `/api/v1`: download, resend, trial and Stripe's webhook, served when KEYGEN_API_TOKEN is set."""

from fastapi import APIRouter

from license import router, stripe_webhook
from license.settings import config

# Localhost on any port, for the site run locally.
LOCAL_ORIGINS = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def license_portal() -> APIRouter | None:
    """None without the Keygen admin token, so a backend run without licenses serves none."""
    if not config.KEYGEN_API_TOKEN:
        return None
    portal = APIRouter(prefix="/api/v1")
    portal.include_router(router.router)
    portal.include_router(stripe_webhook.router)
    return portal


def site_origins() -> list[str]:
    """The site the license pages are on, and its www or bare twin."""
    site = config.NEXT_FRONTEND_URL.rstrip("/")
    if not site:
        return []
    if "://www." in site:
        return [site, site.replace("://www.", "://", 1)]
    return [site, site.replace("://", "://www.", 1)]
