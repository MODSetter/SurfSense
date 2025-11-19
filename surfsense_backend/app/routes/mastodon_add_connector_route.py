"""
Mastodon/ActivityPub connector authentication route.

This route allows users to add a Mastodon connector by providing
their instance URL and access token.

Works with Mastodon, Pixelfed, and other Mastodon-compatible instances.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.mastodon_connector import MastodonConnector
from app.db import SearchSourceConnector, SearchSourceConnectorType, User, get_async_session
from app.users import current_active_user

router = APIRouter()


class MastodonConnectorRequest(BaseModel):
    """Request model for adding a Mastodon connector."""

    search_space_id: int
    instance_url: str  # e.g., https://mastodon.social
    access_token: str
    name: str = "Mastodon"


class MastodonConnectorResponse(BaseModel):
    """Response model for Mastodon connector creation."""

    id: int
    name: str
    connector_type: str
    message: str
    username: str


@router.post("/auth/mastodon/add", response_model=MastodonConnectorResponse)
async def add_mastodon_connector(
    request: MastodonConnectorRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Add a Mastodon/ActivityPub connector.

    This endpoint allows users to connect their Mastodon, Pixelfed, or other
    ActivityPub-compatible account by providing the instance URL and access token.

    To create an access token:
    1. Go to your Mastodon instance Settings → Development → New Application
    2. Give it a name (e.g., "SurfSense")
    3. Select read scopes: read:accounts, read:bookmarks, read:favourites, read:statuses
    4. Create the application and copy the access token

    Args:
        request: The connector configuration
        user: Current authenticated user
        session: Database session

    Returns:
        MastodonConnectorResponse with connector details
    """
    # Validate and normalize URL
    instance_url = request.instance_url.rstrip("/")
    if not instance_url.startswith(("http://", "https://")):
        instance_url = f"https://{instance_url}"

    # Test connection to Mastodon
    mastodon_client = MastodonConnector(
        instance_url=instance_url,
        access_token=request.access_token,
    )

    # Verify credentials and get account info
    account, error = await mastodon_client.verify_credentials()
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect to Mastodon: {error}",
        )

    # Get username and display name
    username = account.get("acct", "unknown")
    display_name = account.get("display_name", username)

    # Create connector config
    connector_config = {
        "INSTANCE_URL": instance_url,
        "ACCESS_TOKEN": request.access_token,
        "ACCOUNT_ID": account.get("id"),
        "USERNAME": username,
    }

    # Use display name or provided name
    connector_name = request.name if request.name != "Mastodon" else f"Mastodon (@{username})"

    # Create the connector in the database
    db_connector = SearchSourceConnector(
        name=connector_name,
        connector_type=SearchSourceConnectorType.MASTODON_CONNECTOR,
        config=connector_config,
        search_space_id=request.search_space_id,
        user_id=str(user.id),
        is_indexable=True,
    )

    session.add(db_connector)
    await session.commit()
    await session.refresh(db_connector)

    return MastodonConnectorResponse(
        id=db_connector.id,
        name=db_connector.name,
        connector_type=db_connector.connector_type.value,
        message=f"Successfully connected to {instance_url} as @{username}",
        username=username,
    )


@router.post("/auth/mastodon/test")
async def test_mastodon_connection(
    instance_url: str,
    access_token: str,
    user: User = Depends(current_active_user),
):
    """
    Test connection to a Mastodon instance.

    This endpoint allows users to verify their credentials before
    creating a connector.

    Args:
        instance_url: Mastodon instance URL
        access_token: User access token
        user: Current authenticated user

    Returns:
        Connection status and account info
    """
    # Normalize URL
    instance_url = instance_url.rstrip("/")
    if not instance_url.startswith(("http://", "https://")):
        instance_url = f"https://{instance_url}"

    # Test connection
    mastodon_client = MastodonConnector(
        instance_url=instance_url,
        access_token=access_token,
    )

    account, error = await mastodon_client.verify_credentials()
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Connection failed: {error}",
        )

    # Get instance info
    instance_info, _ = await mastodon_client.get_instance_info()

    return {
        "status": "success",
        "message": "Successfully connected to Mastodon",
        "account_info": {
            "username": account.get("acct", "unknown"),
            "display_name": account.get("display_name", ""),
            "followers_count": account.get("followers_count", 0),
            "following_count": account.get("following_count", 0),
            "statuses_count": account.get("statuses_count", 0),
        },
        "instance_info": {
            "title": instance_info.get("title", "Unknown") if instance_info else "Unknown",
            "version": instance_info.get("version", "Unknown") if instance_info else "Unknown",
        },
    }
