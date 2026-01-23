"""
Composio Connector OAuth Routes.

Handles OAuth flow for Composio-based integrations (Google Drive, Gmail, Calendar, etc.).
This provides a single connector that can connect to any Composio toolkit.

Endpoints:
- GET /composio/toolkits - List available Composio toolkits
- GET /auth/composio/connector/add - Initiate OAuth for a specific toolkit
- GET /auth/composio/connector/callback - Handle OAuth callback
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.services.composio_service import (
    COMPOSIO_TOOLKIT_NAMES,
    INDEXABLE_TOOLKITS,
    ComposioService,
)
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize security utilities
_state_manager = None


def get_state_manager() -> OAuthStateManager:
    """Get or create OAuth state manager instance."""
    global _state_manager
    if _state_manager is None:
        if not config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set for OAuth security")
        _state_manager = OAuthStateManager(config.SECRET_KEY)
    return _state_manager


@router.get("/composio/toolkits")
async def list_composio_toolkits(user: User = Depends(current_active_user)):
    """
    List available Composio toolkits.

    Returns:
        JSON with list of available toolkits and their metadata.
    """
    if not ComposioService.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Composio integration is not enabled. Set COMPOSIO_ENABLED=TRUE and provide COMPOSIO_API_KEY.",
        )

    try:
        service = ComposioService()
        toolkits = service.list_available_toolkits()
        return {"toolkits": toolkits}
    except Exception as e:
        logger.error(f"Failed to list Composio toolkits: {e!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list toolkits: {e!s}"
        ) from e


@router.get("/auth/composio/connector/add")
async def initiate_composio_auth(
    space_id: int,
    toolkit_id: str = Query(
        ..., description="Composio toolkit ID (e.g., 'googledrive', 'gmail')"
    ),
    user: User = Depends(current_active_user),
):
    """
    Initiate Composio OAuth flow for a specific toolkit.

    Query params:
        space_id: Search space ID to add connector to
        toolkit_id: Composio toolkit ID (e.g., "googledrive", "gmail", "googlecalendar")

    Returns:
        JSON with auth_url to redirect user to Composio authorization
    """
    if not ComposioService.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Composio integration is not enabled.",
        )

    if not space_id:
        raise HTTPException(status_code=400, detail="space_id is required")

    if toolkit_id not in COMPOSIO_TOOLKIT_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown toolkit: {toolkit_id}. Available: {list(COMPOSIO_TOOLKIT_NAMES.keys())}",
        )

    if not config.SECRET_KEY:
        raise HTTPException(
            status_code=500, detail="SECRET_KEY not configured for OAuth security."
        )

    try:
        # Generate secure state parameter with HMAC signature
        state_manager = get_state_manager()
        state_encoded = state_manager.generate_secure_state(
            space_id, user.id, toolkit_id=toolkit_id
        )

        # Build callback URL
        callback_url = config.COMPOSIO_REDIRECT_URI
        if not callback_url:
            # Fallback: construct from BACKEND_URL
            backend_url = config.BACKEND_URL or "http://localhost:8000"
            callback_url = f"{backend_url}/api/v1/auth/composio/connector/callback"

        # Initiate Composio OAuth
        service = ComposioService()
        # Use user.id as the entity ID in Composio (converted to string for Composio)
        entity_id = f"surfsense_{user.id}"

        connection_result = await service.initiate_connection(
            user_id=entity_id,
            toolkit_id=toolkit_id,
            redirect_uri=f"{callback_url}?state={state_encoded}",
        )

        auth_url = connection_result.get("redirect_url")
        if not auth_url:
            raise HTTPException(
                status_code=500, detail="Failed to get authorization URL from Composio"
            )

        logger.info(
            f"Initiating Composio OAuth for user {user.id}, toolkit {toolkit_id}, space {space_id}"
        )
        return {"auth_url": auth_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate Composio OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Composio OAuth: {e!s}"
        ) from e


@router.get("/auth/composio/connector/callback")
async def composio_callback(
    state: str | None = None,
    composio_connected_account_id: str | None = Query(
        None, alias="connectedAccountId"
    ),  # Composio sends camelCase
    connected_account_id: str | None = None,  # Fallback snake_case
    error: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Composio OAuth callback.

    Query params:
        state: Encoded state with space_id, user_id, and toolkit_id
        connected_account_id: Composio connected account ID (may not be present)
        error: OAuth error (if user denied access or error occurred)

    Returns:
        Redirect to frontend success page
    """
    try:
        # Handle OAuth errors
        if error:
            logger.warning(f"Composio OAuth error: {error}")
            space_id = None
            if state:
                try:
                    state_manager = get_state_manager()
                    data = state_manager.validate_state(state)
                    space_id = data.get("space_id")
                except Exception:
                    logger.warning("Failed to validate state in error handler")

            if space_id:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=composio_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=composio_oauth_denied"
                )

        # Validate required parameters
        if not state:
            raise HTTPException(status_code=400, detail="Missing state parameter")

        # Validate and decode state with signature verification
        state_manager = get_state_manager()
        try:
            data = state_manager.validate_state(state)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid state parameter: {e!s}"
            ) from e

        user_id = UUID(data["user_id"])
        space_id = data["space_id"]
        toolkit_id = data.get("toolkit_id")

        if not toolkit_id:
            raise HTTPException(status_code=400, detail="Missing toolkit_id in state")

        toolkit_name = COMPOSIO_TOOLKIT_NAMES.get(toolkit_id, toolkit_id)

        logger.info(
            f"Processing Composio callback for user {user_id}, toolkit {toolkit_id}, space {space_id}"
        )

        # Initialize Composio service
        ComposioService()

        # Use camelCase param if provided (Composio's format), fallback to snake_case
        final_connected_account_id = (
            composio_connected_account_id or connected_account_id
        )

        # DEBUG: Log all query parameters received
        logger.info(
            f"DEBUG: Callback received - connectedAccountId: {composio_connected_account_id}, connected_account_id: {connected_account_id}, using: {final_connected_account_id}"
        )

        # If we still don't have a connected_account_id, warn but continue
        # (the connector will be created but indexing won't work until updated)
        if not final_connected_account_id:
            logger.warning(
                f"Could not find connected_account_id for toolkit {toolkit_id}. "
                "The connector will be created but indexing may not work."
            )
        else:
            logger.info(
                f"Successfully got connected_account_id: {final_connected_account_id}"
            )

        # Build connector config
        connector_config = {
            "composio_connected_account_id": final_connected_account_id,
            "toolkit_id": toolkit_id,
            "toolkit_name": toolkit_name,
            "is_indexable": toolkit_id in INDEXABLE_TOOLKITS,
        }

        # Check for duplicate connector
        # For Composio, we use toolkit_id + connected_account_id as unique identifier
        identifier = final_connected_account_id or f"{toolkit_id}_{user_id}"

        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.COMPOSIO_CONNECTOR,
            space_id,
            user_id,
            identifier,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Composio connector detected for user {user_id} with toolkit {toolkit_id}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=composio-connector"
            )

        try:
            # Generate a unique, user-friendly connector name
            connector_name = await generate_unique_connector_name(
                session,
                SearchSourceConnectorType.COMPOSIO_CONNECTOR,
                space_id,
                user_id,
                f"{toolkit_name} (Composio)",
            )

            db_connector = SearchSourceConnector(
                name=connector_name,
                connector_type=SearchSourceConnectorType.COMPOSIO_CONNECTOR,
                config=connector_config,
                search_space_id=space_id,
                user_id=user_id,
                is_indexable=toolkit_id in INDEXABLE_TOOLKITS,
            )

            session.add(db_connector)
            await session.commit()
            await session.refresh(db_connector)

            logger.info(
                f"Successfully created Composio connector {db_connector.id} for user {user_id}, toolkit {toolkit_id}"
            )

            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=composio-connector&connectorId={db_connector.id}"
            )

        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Database integrity error: {e!s}")
            raise HTTPException(
                status_code=409,
                detail=f"Database integrity error: {e!s}",
            ) from e
        except ValidationError as e:
            await session.rollback()
            logger.error(f"Validation error: {e!s}")
            raise HTTPException(
                status_code=400, detail=f"Invalid connector configuration: {e!s}"
            ) from e

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Composio callback: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Composio OAuth: {e!s}"
        ) from e
