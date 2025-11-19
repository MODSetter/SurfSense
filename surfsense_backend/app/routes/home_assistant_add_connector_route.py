"""
Home Assistant connector authentication route.

This route allows users to add a Home Assistant connector by providing
their Home Assistant URL and Long-Lived Access Token.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.home_assistant_connector import HomeAssistantConnector
from app.db import SearchSourceConnector, SearchSourceConnectorType, User, get_async_session
from app.users import current_active_user

router = APIRouter()


class HomeAssistantConnectorRequest(BaseModel):
    """Request model for adding a Home Assistant connector."""

    search_space_id: int
    ha_url: str  # Using str instead of HttpUrl for flexibility with local addresses
    ha_access_token: str
    name: str = "Home Assistant"


class HomeAssistantConnectorResponse(BaseModel):
    """Response model for Home Assistant connector creation."""

    id: int
    name: str
    connector_type: str
    message: str


@router.post("/auth/home-assistant/add", response_model=HomeAssistantConnectorResponse)
async def add_home_assistant_connector(
    request: HomeAssistantConnectorRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Add a Home Assistant connector.

    This endpoint allows users to connect their Home Assistant instance
    by providing the URL and a Long-Lived Access Token.

    To create a Long-Lived Access Token in Home Assistant:
    1. Go to your Home Assistant instance
    2. Click on your profile (bottom left)
    3. Scroll down to "Long-Lived Access Tokens"
    4. Create a new token and copy it

    Args:
        request: The connector configuration
        user: Current authenticated user
        session: Database session

    Returns:
        HomeAssistantConnectorResponse with connector details
    """
    # Validate and normalize URL
    ha_url = request.ha_url.rstrip("/")

    # Test connection to Home Assistant
    ha_client = HomeAssistantConnector(
        ha_url=ha_url,
        access_token=request.ha_access_token,
    )

    connected, error = await ha_client.test_connection()
    if not connected:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect to Home Assistant: {error}",
        )

    # Get Home Assistant config to verify and get instance name
    config, config_error = await ha_client.get_config()
    if config_error:
        # Non-fatal, just use provided name
        instance_name = request.name
    else:
        # Use location name from config if available
        instance_name = config.get("location_name", request.name)

    # Create connector config
    connector_config = {
        "HA_URL": ha_url,
        "HA_ACCESS_TOKEN": request.ha_access_token,
    }

    # Create the connector in the database
    db_connector = SearchSourceConnector(
        name=instance_name,
        connector_type=SearchSourceConnectorType.HOME_ASSISTANT_CONNECTOR,
        config=connector_config,
        search_space_id=request.search_space_id,
        user_id=str(user.id),
        is_indexable=True,
    )

    session.add(db_connector)
    await session.commit()
    await session.refresh(db_connector)

    return HomeAssistantConnectorResponse(
        id=db_connector.id,
        name=db_connector.name,
        connector_type=db_connector.connector_type.value,
        message=f"Successfully connected to Home Assistant at {ha_url}",
    )


@router.post("/auth/home-assistant/test")
async def test_home_assistant_connection(
    ha_url: str,
    ha_access_token: str,
    user: User = Depends(current_active_user),
):
    """
    Test connection to a Home Assistant instance.

    This endpoint allows users to verify their credentials before
    creating a connector.

    Args:
        ha_url: Home Assistant URL
        ha_access_token: Long-Lived Access Token
        user: Current authenticated user

    Returns:
        Connection status and instance info
    """
    # Normalize URL
    ha_url = ha_url.rstrip("/")

    # Test connection
    ha_client = HomeAssistantConnector(
        ha_url=ha_url,
        access_token=ha_access_token,
    )

    connected, error = await ha_client.test_connection()
    if not connected:
        raise HTTPException(
            status_code=400,
            detail=f"Connection failed: {error}",
        )

    # Get config for additional info
    config, _ = await ha_client.get_config()

    return {
        "status": "success",
        "message": "Successfully connected to Home Assistant",
        "instance_info": {
            "location_name": config.get("location_name", "Unknown") if config else "Unknown",
            "version": config.get("version", "Unknown") if config else "Unknown",
            "time_zone": config.get("time_zone", "Unknown") if config else "Unknown",
        },
    }
