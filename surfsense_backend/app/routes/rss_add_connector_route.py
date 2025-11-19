"""
Routes for adding and managing RSS Feed connectors.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.rss_connector import RSSConnector
from app.db import SearchSourceConnector, SearchSourceConnectorType, SearchSpace, User, get_async_session
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/rss", tags=["rss"])


class FeedValidationRequest(BaseModel):
    """Request to validate a feed URL."""

    url: HttpUrl


class FeedValidationResponse(BaseModel):
    """Response from feed validation."""

    url: str
    valid: bool
    title: str
    last_updated: str | None
    item_count: int
    error: str | None


class OPMLImportResponse(BaseModel):
    """Response from OPML import."""

    feeds: list[dict]
    total_count: int


class AddRSSConnectorRequest(BaseModel):
    """Request to add RSS connector."""

    search_space_id: int
    name: str
    feed_urls: list[str]


class AddRSSConnectorResponse(BaseModel):
    """Response from adding RSS connector."""

    connector_id: int
    message: str
    feed_count: int


@router.post("/validate", response_model=FeedValidationResponse)
async def validate_feed(
    request: FeedValidationRequest,
    _user: User = Depends(current_active_user),
):
    """
    Validate an RSS/Atom feed URL.

    Checks if the feed is accessible, parseable, and has content.
    """
    connector = RSSConnector(feed_urls=[])
    result = await connector.validate_feed(str(request.url))

    return FeedValidationResponse(
        url=result["url"],
        valid=result["valid"],
        title=result["title"],
        last_updated=result["last_updated"],
        item_count=result["item_count"],
        error=result["error"],
    )


@router.post("/import-opml", response_model=OPMLImportResponse)
async def import_opml(
    file: UploadFile = File(...),
    _user: User = Depends(current_active_user),
):
    """
    Import feed URLs from an OPML file.

    Returns list of feeds with their metadata (url, title, category).
    Does not validate feeds - use /validate endpoint to check individual feeds.
    """
    if not file.filename or not file.filename.lower().endswith((".opml", ".xml")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an OPML or XML file.",
        )

    try:
        content = await file.read()
        opml_content = content.decode("utf-8")

        feeds = RSSConnector.parse_opml(opml_content)

        return OPMLImportResponse(
            feeds=feeds,
            total_count=len(feeds),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail="Failed to decode file. Please ensure it's a valid UTF-8 encoded OPML file.",
        ) from e


@router.post("/validate-multiple")
async def validate_multiple_feeds(
    feed_urls: list[str],
    _user: User = Depends(current_active_user),
):
    """
    Validate multiple feed URLs.

    Returns validation results for each feed.
    """
    connector = RSSConnector(feed_urls=[])
    results = []

    for url in feed_urls:
        result = await connector.validate_feed(url)
        results.append({
            "url": result["url"],
            "valid": result["valid"],
            "title": result["title"],
            "last_updated": result["last_updated"],
            "item_count": result["item_count"],
            "error": result["error"],
        })

    valid_count = sum(1 for r in results if r["valid"])
    invalid_count = len(results) - valid_count

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "valid": valid_count,
            "invalid": invalid_count,
        },
    }


@router.post("/add", response_model=AddRSSConnectorResponse)
async def add_rss_connector(
    request: AddRSSConnectorRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Add an RSS Feed connector to a search space.

    The connector stores the list of feed URLs and can be indexed
    to fetch and store feed entries.
    """
    # Verify search space exists and belongs to user
    result = await session.execute(
        select(SearchSpace).where(
            SearchSpace.id == request.search_space_id,
            SearchSpace.user_id == user.id,
        )
    )
    search_space = result.scalar_one_or_none()

    if not search_space:
        raise HTTPException(
            status_code=404,
            detail="Search space not found or access denied",
        )

    # Check if RSS connector already exists for this search space
    existing = await session.execute(
        select(SearchSourceConnector).where(
            SearchSourceConnector.search_space_id == request.search_space_id,
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.connector_type == SearchSourceConnectorType.RSS_FEED_CONNECTOR,
        )
    )
    existing_connector = existing.scalar_one_or_none()

    if existing_connector:
        # Update existing connector with new/additional feeds
        current_feeds = existing_connector.config.get("FEED_URLS", [])
        # Merge feeds, avoiding duplicates
        all_feeds = list(set(current_feeds + request.feed_urls))
        existing_connector.config["FEED_URLS"] = all_feeds
        existing_connector.name = request.name

        await session.commit()

        logger.info(
            f"Updated RSS connector {existing_connector.id} with {len(all_feeds)} feeds"
        )

        return AddRSSConnectorResponse(
            connector_id=existing_connector.id,
            message=f"Updated RSS connector with {len(all_feeds)} feeds",
            feed_count=len(all_feeds),
        )

    # Create new connector
    connector = SearchSourceConnector(
        name=request.name,
        connector_type=SearchSourceConnectorType.RSS_FEED_CONNECTOR,
        is_indexable=True,
        config={
            "FEED_URLS": request.feed_urls,
        },
        search_space_id=request.search_space_id,
        user_id=user.id,
    )

    session.add(connector)
    await session.commit()
    await session.refresh(connector)

    logger.info(
        f"Created RSS connector {connector.id} with {len(request.feed_urls)} feeds"
    )

    return AddRSSConnectorResponse(
        connector_id=connector.id,
        message=f"RSS connector created with {len(request.feed_urls)} feeds",
        feed_count=len(request.feed_urls),
    )


@router.get("/{connector_id}/feeds")
async def get_connector_feeds(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get the list of feeds configured for an RSS connector.
    """
    result = await session.execute(
        select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.connector_type == SearchSourceConnectorType.RSS_FEED_CONNECTOR,
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=404,
            detail="RSS connector not found or access denied",
        )

    feed_urls = connector.config.get("FEED_URLS", [])

    return {
        "connector_id": connector.id,
        "name": connector.name,
        "feed_urls": feed_urls,
        "feed_count": len(feed_urls),
    }


@router.put("/{connector_id}/feeds")
async def update_connector_feeds(
    connector_id: int,
    feed_urls: list[str],
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update the list of feeds for an RSS connector.
    """
    result = await session.execute(
        select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.connector_type == SearchSourceConnectorType.RSS_FEED_CONNECTOR,
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=404,
            detail="RSS connector not found or access denied",
        )

    connector.config["FEED_URLS"] = feed_urls
    await session.commit()

    logger.info(f"Updated RSS connector {connector_id} with {len(feed_urls)} feeds")

    return {
        "connector_id": connector.id,
        "message": f"Updated with {len(feed_urls)} feeds",
        "feed_count": len(feed_urls),
    }


@router.delete("/{connector_id}/feeds/{feed_index}")
async def remove_feed_from_connector(
    connector_id: int,
    feed_index: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Remove a specific feed from an RSS connector by index.
    """
    result = await session.execute(
        select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.connector_type == SearchSourceConnectorType.RSS_FEED_CONNECTOR,
        )
    )
    connector = result.scalar_one_or_none()

    if not connector:
        raise HTTPException(
            status_code=404,
            detail="RSS connector not found or access denied",
        )

    feed_urls = connector.config.get("FEED_URLS", [])

    if feed_index < 0 or feed_index >= len(feed_urls):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feed index. Must be between 0 and {len(feed_urls) - 1}",
        )

    removed_url = feed_urls.pop(feed_index)
    connector.config["FEED_URLS"] = feed_urls
    await session.commit()

    logger.info(f"Removed feed {removed_url} from RSS connector {connector_id}")

    return {
        "connector_id": connector.id,
        "removed_feed": removed_url,
        "remaining_feeds": len(feed_urls),
    }
