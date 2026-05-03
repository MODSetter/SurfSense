"""
Composio Connector OAuth Routes.

Handles OAuth flow for Composio-based integrations (Google Drive, Gmail, Calendar, etc.).
This provides a single connector that can connect to any Composio toolkit.

Endpoints:
- GET /composio/toolkits - List available Composio toolkits
- GET /auth/composio/connector/add - Initiate OAuth for a specific toolkit
- GET /auth/composio/connector/callback - Handle OAuth callback
- GET /connectors/{connector_id}/composio-drive/folders - List folders/files for Composio Google Drive
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

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
    TOOLKIT_TO_CONNECTOR_TYPE,
    ComposioService,
)
from app.users import current_active_user
from app.utils.connector_naming import (
    count_connectors_of_type,
    get_base_name_for_type,
)
from app.utils.oauth_security import OAuthStateManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Map toolkit_id to frontend connector ID
TOOLKIT_TO_FRONTEND_CONNECTOR_ID = {
    "googledrive": "composio-googledrive",
    "gmail": "composio-gmail",
    "googlecalendar": "composio-googlecalendar",
}

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
    request: Request,
    state: str | None = None,
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?error=composio_oauth_denied"
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
        service = ComposioService()

        # Extract connected_account_id from query params (accepts both camelCase and snake_case)
        query_params = request.query_params
        final_connected_account_id = query_params.get(
            "connectedAccountId"
        ) or query_params.get("connected_account_id")

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
            # Wait for Composio to finish exchanging the auth code for tokens.
            try:
                service.wait_for_connection(final_connected_account_id, timeout=30.0)
            except Exception:
                logger.warning(
                    f"wait_for_connection timed out for {final_connected_account_id}, "
                    "proceeding anyway",
                    exc_info=True,
                )

        # Build entity_id for Composio API calls (same format as used in initiate)
        entity_id = f"surfsense_{user_id}"

        # Build connector config
        connector_config = {
            "composio_connected_account_id": final_connected_account_id,
            "toolkit_id": toolkit_id,
            "toolkit_name": toolkit_name,
            "is_indexable": toolkit_id in INDEXABLE_TOOLKITS,
        }

        # Get the specific connector type for this toolkit
        connector_type_str = TOOLKIT_TO_CONNECTOR_TYPE.get(toolkit_id)
        if not connector_type_str:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown toolkit: {toolkit_id}. Available: {list(TOOLKIT_TO_CONNECTOR_TYPE.keys())}",
            )
        connector_type = SearchSourceConnectorType(connector_type_str)

        # Get the base name for this connector type (e.g., "Google Drive", "Gmail")
        base_name = get_base_name_for_type(connector_type)

        # FIRST: Get the email for this connected account
        # This is needed to determine if it's a reconnection (same email) or new account
        email = None
        try:
            email = await service.get_connected_account_email(
                connected_account_id=final_connected_account_id,
                entity_id=entity_id,
                toolkit_id=toolkit_id,
            )
            if email:
                logger.info(f"Retrieved email {email} for {toolkit_id} connector")
        except Exception as email_error:
            logger.warning(f"Could not get email for connector: {email_error!s}")

        # Generate the connector name (with email if available)
        # Format: "Gmail (Composio) - john@gmail.com" or "Gmail (Composio) 1" if no email
        if email:
            connector_name = f"{base_name} (Composio) - {email}"
        else:
            # Fallback to generic naming if email not available
            count = await count_connectors_of_type(
                session, connector_type, space_id, user_id
            )
            if count == 0:
                connector_name = f"{base_name} (Composio) 1"
            else:
                connector_name = f"{base_name} (Composio) {count + 1}"

        # Check if a connector with this SAME name already exists (reconnection case)
        # This allows multiple accounts (different emails) while supporting reconnection
        existing_connector_result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.connector_type == connector_type,
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.name == connector_name,
            )
        )
        existing_connector = existing_connector_result.scalars().first()

        if existing_connector:
            # This is a RECONNECTION of the same account - update existing connector
            old_connected_account_id = existing_connector.config.get(
                "composio_connected_account_id"
            )
            if (
                old_connected_account_id
                and old_connected_account_id != final_connected_account_id
            ):
                try:
                    deleted = await service.delete_connected_account(
                        old_connected_account_id
                    )
                    if deleted:
                        logger.info(
                            f"Deleted old Composio connected account {old_connected_account_id} "
                            f"before updating connector {existing_connector.id}"
                        )
                except Exception as delete_error:
                    logger.warning(
                        f"Error deleting old Composio connected account {old_connected_account_id}: {delete_error!s}"
                    )

            # Update existing connector with new connected_account_id
            # Merge new credentials with existing config to preserve user settings
            logger.info(
                f"Reconnecting existing Composio connector {existing_connector.id} ({connector_name}) "
                f"with new connected_account_id {final_connected_account_id}"
            )
            existing_config = (
                existing_connector.config.copy() if existing_connector.config else {}
            )
            existing_config.update(connector_config)
            existing_connector.config = existing_config

            flag_modified(existing_connector, "config")
            await session.commit()
            await session.refresh(existing_connector)

            frontend_connector_id = TOOLKIT_TO_FRONTEND_CONNECTOR_ID.get(
                toolkit_id, "composio-connector"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?success=true&connector={frontend_connector_id}&connectorId={existing_connector.id}"
            )

        # This is a NEW account - create a new connector
        try:
            logger.info(f"Creating new Composio connector: {connector_name}")

            db_connector = SearchSourceConnector(
                name=connector_name,
                connector_type=connector_type,
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

            # Get the frontend connector ID based on toolkit_id
            frontend_connector_id = TOOLKIT_TO_FRONTEND_CONNECTOR_ID.get(
                toolkit_id, "composio-connector"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?success=true&connector={frontend_connector_id}&connectorId={db_connector.id}"
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


COMPOSIO_CONNECTOR_TYPES = {
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
}


@router.get("/auth/composio/connector/reauth")
async def reauth_composio_connector(
    space_id: int,
    connector_id: int,
    return_url: str | None = None,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Initiate Composio re-authentication for an expired connected account.

    Uses Composio's refresh API so the same connected_account_id stays valid
    after the user completes the OAuth flow again.

    Query params:
        space_id: Search space ID the connector belongs to
        connector_id: ID of the existing Composio connector to re-authenticate
        return_url: Optional frontend path to redirect to after completion
    """
    if not ComposioService.is_enabled():
        raise HTTPException(
            status_code=503, detail="Composio integration is not enabled."
        )

    if not config.SECRET_KEY:
        raise HTTPException(
            status_code=500, detail="SECRET_KEY not configured for OAuth security."
        )

    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.connector_type.in_(COMPOSIO_CONNECTOR_TYPES),
            )
        )
        connector = result.scalars().first()
        if not connector:
            raise HTTPException(
                status_code=404,
                detail="Composio connector not found or access denied",
            )

        connected_account_id = connector.config.get("composio_connected_account_id")
        if not connected_account_id:
            raise HTTPException(
                status_code=400,
                detail="Composio connected account ID not found. Please reconnect the connector.",
            )

        # Build callback URL with secure state
        state_manager = get_state_manager()
        state_encoded = state_manager.generate_secure_state(
            space_id,
            user.id,
            toolkit_id=connector.config.get("toolkit_id", ""),
            connector_id=connector_id,
            return_url=return_url,
        )

        callback_base = config.COMPOSIO_REDIRECT_URI
        if not callback_base:
            backend_url = config.BACKEND_URL or "http://localhost:8000"
            callback_base = (
                f"{backend_url}/api/v1/auth/composio/connector/reauth/callback"
            )
        else:
            # Replace the normal callback path with the reauth one
            callback_base = callback_base.replace(
                "/auth/composio/connector/callback",
                "/auth/composio/connector/reauth/callback",
            )

        callback_url = f"{callback_base}?state={state_encoded}"

        service = ComposioService()
        refresh_result = service.refresh_connected_account(
            connected_account_id=connected_account_id,
            redirect_url=callback_url,
        )

        if refresh_result["redirect_url"] is None:
            # Token refreshed server-side; clear auth_expired immediately
            if connector.config.get("auth_expired"):
                connector.config = {**connector.config, "auth_expired": False}
                flag_modified(connector, "config")
                await session.commit()
            logger.info(
                f"Composio account {connected_account_id} refreshed server-side (no redirect needed)"
            )
            return {
                "success": True,
                "message": "Authentication refreshed successfully.",
            }

        logger.info(f"Initiating Composio re-auth for connector {connector_id}")
        return {"auth_url": refresh_result["redirect_url"]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate Composio re-auth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Composio re-auth: {e!s}"
        ) from e


@router.get("/auth/composio/connector/reauth/callback")
async def composio_reauth_callback(
    request: Request,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Composio re-authentication callback.

    Clears the auth_expired flag and redirects the user back to the frontend.
    The connected_account_id has not changed — Composio refreshed it in place.
    """
    try:
        if not state:
            raise HTTPException(status_code=400, detail="Missing state parameter")

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
        reauth_connector_id = data.get("connector_id")
        return_url = data.get("return_url")

        if not reauth_connector_id:
            raise HTTPException(status_code=400, detail="Missing connector_id in state")

        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == reauth_connector_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.search_space_id == space_id,
            )
        )
        connector = result.scalars().first()
        if not connector:
            raise HTTPException(
                status_code=404,
                detail="Connector not found or access denied during re-auth callback",
            )

        # Wait for Composio to finish processing new tokens before proceeding.
        # Without this, get_access_token() may return stale credentials.
        connected_account_id = connector.config.get("composio_connected_account_id")
        if connected_account_id:
            try:
                service = ComposioService()
                service.wait_for_connection(connected_account_id, timeout=30.0)
            except Exception:
                logger.warning(
                    f"wait_for_connection timed out for connector {reauth_connector_id}, "
                    "proceeding anyway — tokens may not be ready yet",
                    exc_info=True,
                )

        # Clear auth_expired flag
        connector.config = {**connector.config, "auth_expired": False}
        flag_modified(connector, "config")
        await session.commit()
        await session.refresh(connector)

        logger.info(f"Composio re-auth completed for connector {reauth_connector_id}")

        if return_url and return_url.startswith("/"):
            return RedirectResponse(url=f"{config.NEXT_FRONTEND_URL}{return_url}")

        frontend_connector_id = TOOLKIT_TO_FRONTEND_CONNECTOR_ID.get(
            connector.config.get("toolkit_id", ""), "composio-connector"
        )
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?success=true&connector={frontend_connector_id}&connectorId={reauth_connector_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Composio reauth callback: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Composio re-auth: {e!s}"
        ) from e


@router.get("/connectors/{connector_id}/composio-drive/folders")
async def list_composio_drive_folders(
    connector_id: int,
    parent_id: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List folders AND files in user's Google Drive via Composio.

    Uses Composio's Google Drive tool execution path so managed OAuth tokens
    do not need to be exposed through connected account state.
    """
    if not ComposioService.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Composio integration is not enabled.",
        )

    connector = None
    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="Composio Google Drive connector not found or access denied",
            )

        composio_connected_account_id = connector.config.get(
            "composio_connected_account_id"
        )
        if not composio_connected_account_id:
            raise HTTPException(
                status_code=400,
                detail="Composio connected account not found. Please reconnect the connector.",
            )

        service = ComposioService()
        entity_id = f"surfsense_{user.id}"
        items = []
        page_token = None
        error = None

        while True:
            page_items, next_token, page_error = await service.get_drive_files(
                connected_account_id=composio_connected_account_id,
                entity_id=entity_id,
                folder_id=parent_id,
                page_token=page_token,
                page_size=100,
            )
            if page_error:
                error = page_error
                break

            items.extend(page_items)
            if not next_token:
                break
            page_token = next_token

        for item in items:
            item["isFolder"] = (
                item.get("mimeType") == "application/vnd.google-apps.folder"
            )

        items.sort(
            key=lambda item: (not item["isFolder"], item.get("name", "").lower())
        )

        if error:
            error_lower = error.lower()
            if (
                "401" in error
                or "invalid_grant" in error_lower
                or "token has been expired or revoked" in error_lower
                or "invalid credentials" in error_lower
                or "authentication failed" in error_lower
            ):
                try:
                    if connector and not connector.config.get("auth_expired"):
                        connector.config = {**connector.config, "auth_expired": True}
                        flag_modified(connector, "config")
                        await session.commit()
                        logger.info(
                            f"Marked Composio connector {connector_id} as auth_expired"
                        )
                except Exception:
                    logger.warning(
                        f"Failed to persist auth_expired for connector {connector_id}",
                        exc_info=True,
                    )
                raise HTTPException(
                    status_code=400,
                    detail="Google Drive authentication expired. Please re-authenticate.",
                )
            raise HTTPException(
                status_code=500, detail=f"Failed to list folder contents: {error}"
            )

        folder_count = sum(1 for item in items if item.get("isFolder", False))
        file_count = len(items) - folder_count

        logger.info(
            f"Listed {len(items)} total items ({folder_count} folders, {file_count} files) for Composio connector {connector_id}"
            + (f" in folder {parent_id}" if parent_id else " in ROOT")
        )

        return {"items": items}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Composio Drive contents: {e!s}", exc_info=True)
        error_lower = str(e).lower()
        if (
            "invalid_grant" in error_lower
            or "token has been expired or revoked" in error_lower
            or "invalid credentials" in error_lower
            or "authentication failed" in error_lower
            or "401" in str(e)
        ):
            try:
                if connector and not connector.config.get("auth_expired"):
                    connector.config = {**connector.config, "auth_expired": True}
                    flag_modified(connector, "config")
                    await session.commit()
                    logger.info(
                        f"Marked Composio connector {connector_id} as auth_expired"
                    )
            except Exception:
                logger.warning(
                    f"Failed to persist auth_expired for connector {connector_id}",
                    exc_info=True,
                )
            raise HTTPException(
                status_code=400,
                detail="Google Drive authentication expired. Please re-authenticate.",
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Failed to list Drive contents: {e!s}"
        ) from e
