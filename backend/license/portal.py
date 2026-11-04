"""The license portal at `/api/v1`: download, resend, trial, the app's refresh and its job packs, and Stripe's webhook, served when KEYGEN_API_TOKEN is set."""

from fastapi import APIRouter

from license import refresh_route, router, stripe_webhook
from license.job_packs import route as job_pack_route
from license.settings import config
from license.token_bucket import forgetting_idle_buckets

# Localhost on any port, for the site run locally.
LOCAL_ORIGINS = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def license_portal() -> APIRouter | None:
    """None without a Keygen token, so a backend run without licenses serves none."""
    if not config.KEYGEN_API_TOKEN:
        return None
    # The app that includes it runs this lifespan inside its own.
    portal = APIRouter(prefix="/api/v1", lifespan=forgetting_idle_buckets)
    portal.include_router(router.router)
    portal.include_router(refresh_route.router)
    portal.include_router(job_pack_route.router)
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
