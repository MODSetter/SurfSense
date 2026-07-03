"""Google Maps scraper routes (Apify actor-compatible)."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth.context import AuthContext
from app.proprietary.scrapers.google_maps import (
    GoogleMapsReviewsInput,
    GoogleMapsScrapeInput,
    scrape_places,
    scrape_reviews,
)
from app.proprietary.scrapers.google_maps.scraper import SignInRequiredError
from app.users import require_session_context

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/google-maps/scrape")
async def scrape_places_route(
    payload: GoogleMapsScrapeInput,
    _auth: AuthContext = Depends(require_session_context),
) -> list[dict]:
    """Scrape Google Maps places (search terms / URLs / place IDs).

    Apify "Google Maps Scraper"-compatible input/output. Runs inline and is
    bounded only by the request's own ``maxCrawledPlacesPerSearch``.
    """
    try:
        return await scrape_places(payload)
    except SignInRequiredError as e:
        raise HTTPException(
            status_code=403, detail=f"Google sign in required: {e!s}"
        ) from e
    except Exception as e:
        logger.error("Google Maps scrape failed: %s", e)
        raise HTTPException(
            status_code=502, detail=f"Google Maps scrape failed: {e!s}"
        ) from e


@router.post("/google-maps/reviews")
async def scrape_reviews_route(
    payload: GoogleMapsReviewsInput,
    _auth: AuthContext = Depends(require_session_context),
) -> list[dict]:
    """Scrape Google Maps reviews for the given place URLs / place IDs.

    Apify "Google Maps Reviews Scraper"-compatible. Runs inline and is bounded
    only by the request's own ``maxReviews``.
    """
    try:
        return await scrape_reviews(payload)
    except SignInRequiredError as e:
        raise HTTPException(
            status_code=403, detail=f"Google sign in required: {e!s}"
        ) from e
    except Exception as e:
        logger.error("Google Maps reviews scrape failed: %s", e)
        raise HTTPException(
            status_code=502, detail=f"Google Maps reviews scrape failed: {e!s}"
        ) from e
