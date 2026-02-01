"""
Slack Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Slack connector.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.schemas.slack_auth_credentials import SlackAuthCredentialsBase
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    extract_identifier_from_credentials,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

# Slack OAuth endpoints
AUTHORIZATION_URL = "https://slack.com/oauth/v2/authorize"
TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# OAuth scopes for Slack (Bot Token)
SCOPES = [
    "channels:history",  # Read messages in public channels
    "channels:read",  # View basic information about public channels
    "groups:history",  # Read messages in private channels
    "groups:read",  # View basic information about private channels
    "im:history",  # Read messages in direct messages
    "mpim:history",  # Read messages in group direct messages
    "users:read",  # Read user information
]

# Initialize security utilities
_state_manager = None
_token_encryption = None


def get_state_manager() -> OAuthStateManager:
    """Get or create OAuth state manager instance."""
    global _state_manager
    if _state_manager is None:
        if not config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set for OAuth security")
        _state_manager = OAuthStateManager(config.SECRET_KEY)
    return _state_manager


def get_token_encryption() -> TokenEncryption:
    """Get or create token encryption instance."""
    global _token_encryption
    if _token_encryption is None:
        if not config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set for token encryption")
        _token_encryption = TokenEncryption(config.SECRET_KEY)
    return _token_encryption


@router.get("/auth/slack/connector/add")
async def connect_slack(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Slack OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.SLACK_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Slack OAuth not configured.")

        if not config.SECRET_KEY:
            raise HTTPException(
                status_code=500, detail="SECRET_KEY not configured for OAuth security."
            )

        # Generate secure state parameter with HMAC signature
        state_manager = get_state_manager()
        state_encoded = state_manager.generate_secure_state(space_id, user.id)

        # Build authorization URL
        from urllib.parse import urlencode

        auth_params = {
            "client_id": config.SLACK_CLIENT_ID,
            "scope": ",".join(SCOPES),
            "redirect_uri": config.SLACK_REDIRECT_URI,
            "state": state_encoded,
        }

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(f"Generated Slack OAuth URL for user {user.id}, space {space_id}")
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate Slack OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Slack OAuth: {e!s}"
        ) from e


@router.get("/auth/slack/connector/callback")
async def slack_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Slack OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from Slack (if user granted access)
        error: Error code from Slack (if user denied access or error occurred)
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Slack OAuth error: {error}")
            # Try to decode state to get space_id for redirect, but don't fail if it's invalid
            space_id = None
            if state:
                try:
                    state_manager = get_state_manager()
                    data = state_manager.validate_state(state)
                    space_id = data.get("space_id")
                except Exception:
                    # If state is invalid, we'll redirect without space_id
                    logger.warning("Failed to validate state in error handler")

            # Redirect to frontend with error parameter
            if space_id:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=slack_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=slack_oauth_denied"
                )

        # Validate required parameters for successful flow
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")
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

        # Validate redirect URI (security: ensure it matches configured value)
        if not config.SLACK_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="SLACK_REDIRECT_URI not configured"
            )

        # Exchange authorization code for access token
        token_data = {
            "client_id": config.SLACK_CLIENT_ID,
            "client_secret": config.SLACK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": config.SLACK_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

        if token_response.status_code != 200:
            error_detail = token_response.text
            try:
                error_json = token_response.json()
                error_detail = error_json.get("error", error_detail)
            except Exception:
                pass
            raise HTTPException(
                status_code=400, detail=f"Token exchange failed: {error_detail}"
            )

        token_json = token_response.json()

        # Slack OAuth v2 returns success status in the JSON
        if not token_json.get("ok", False):
            error_msg = token_json.get("error", "Unknown error")
            raise HTTPException(
                status_code=400, detail=f"Slack OAuth error: {error_msg}"
            )

        # Extract bot token from Slack response
        # Slack OAuth v2 returns: { "ok": true, "access_token": "...", "bot": { "bot_user_id": "...", "bot_access_token": "xoxb-..." }, "refresh_token": "...", ... }
        bot_token = None
        if token_json.get("bot") and token_json["bot"].get("bot_access_token"):
            bot_token = token_json["bot"]["bot_access_token"]
        elif token_json.get("access_token"):
            # Fallback to access_token if bot token not available
            bot_token = token_json["access_token"]
        else:
            raise HTTPException(
                status_code=400, detail="No bot token received from Slack"
            )

        # Extract refresh token if available (for token rotation)
        refresh_token = token_json.get("refresh_token")

        # Encrypt sensitive tokens before storing
        token_encryption = get_token_encryption()

        # Calculate expiration time (UTC, tz-aware)
        # Slack tokens don't expire by default, but we'll store expiration info if provided
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Store the encrypted bot token and refresh token in connector config
        connector_config = {
            "bot_token": token_encryption.encrypt_token(bot_token),
            "refresh_token": token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            "bot_user_id": token_json.get("bot", {}).get("bot_user_id"),
            "team_id": token_json.get("team", {}).get("id"),
            "team_name": token_json.get("team", {}).get("name"),
            "token_type": token_json.get("token_type", "Bearer"),
            "expires_in": token_json.get("expires_in"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": token_json.get("scope"),
            # Mark that tokens are encrypted for backward compatibility
            "_token_encrypted": True,
        }

        # Extract unique identifier from connector credentials
        connector_identifier = extract_identifier_from_credentials(
            SearchSourceConnectorType.SLACK_CONNECTOR, connector_config
        )

        # Check for duplicate connector (same workspace already connected)
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.SLACK_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Slack connector detected for user {user_id} with workspace {connector_identifier}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=slack-connector"
            )

        # Generate a unique, user-friendly connector name
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.SLACK_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )

        # Create new connector
        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.SLACK_CONNECTOR,
            is_indexable=True,
            config=connector_config,
            search_space_id=space_id,
            user_id=user_id,
        )
        session.add(new_connector)
        logger.info(
            f"Created new Slack connector for user {user_id} in space {space_id}"
        )

        try:
            await session.commit()
            logger.info(f"Successfully saved Slack connector for user {user_id}")

            # Redirect to the frontend with success params
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=slack-connector&connectorId={new_connector.id}"
            )

        except ValidationError as e:
            await session.rollback()
            raise HTTPException(
                status_code=422, detail=f"Validation error: {e!s}"
            ) from e
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Database integrity error: {e!s}",
            ) from e
        except Exception as e:
            logger.error(f"Failed to create search source connector: {e!s}")
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create search source connector: {e!s}",
            ) from e

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete Slack OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Slack OAuth: {e!s}"
        ) from e


async def refresh_slack_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
    """
    Refresh the Slack bot token for a connector.

    Args:
        session: Database session
        connector: Slack connector to refresh

    Returns:
        Updated connector object
    """
    try:
        logger.info(f"Refreshing Slack token for connector {connector.id}")

        credentials = SlackAuthCredentialsBase.from_dict(connector.config)

        # Decrypt tokens if they are encrypted
        token_encryption = get_token_encryption()
        is_encrypted = connector.config.get("_token_encrypted", False)

        refresh_token = credentials.refresh_token
        if is_encrypted and refresh_token:
            try:
                refresh_token = token_encryption.decrypt_token(refresh_token)
            except Exception as e:
                logger.error(f"Failed to decrypt refresh token: {e!s}")
                raise HTTPException(
                    status_code=500, detail="Failed to decrypt stored refresh token"
                ) from e

        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail="No refresh token available. Please re-authenticate.",
            )

        # Slack uses oauth.v2.access for token refresh with grant_type=refresh_token
        refresh_data = {
            "client_id": config.SLACK_CLIENT_ID,
            "client_secret": config.SLACK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                data=refresh_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

        if token_response.status_code != 200:
            error_detail = token_response.text
            try:
                error_json = token_response.json()
                error_detail = error_json.get("error", error_detail)
            except Exception:
                pass
            # Check if this is a token expiration/revocation error
            error_lower = error_detail.lower()
            if (
                "invalid_grant" in error_lower
                or "invalid_auth" in error_lower
                or "token_revoked" in error_lower
                or "expired" in error_lower
                or "revoked" in error_lower
            ):
                raise HTTPException(
                    status_code=401,
                    detail="Slack authentication failed. Please re-authenticate.",
                )
            raise HTTPException(
                status_code=400, detail=f"Token refresh failed: {error_detail}"
            )

        token_json = token_response.json()

        # Slack OAuth v2 returns success status in the JSON
        if not token_json.get("ok", False):
            error_msg = token_json.get("error", "Unknown error")
            # Check if this is a token expiration/revocation error
            error_lower = error_msg.lower()
            if (
                "invalid_grant" in error_lower
                or "invalid_auth" in error_lower
                or "invalid_refresh_token" in error_lower
                or "token_revoked" in error_lower
                or "expired" in error_lower
                or "revoked" in error_lower
            ):
                raise HTTPException(
                    status_code=401,
                    detail="Slack authentication failed. Please re-authenticate.",
                )
            raise HTTPException(
                status_code=400, detail=f"Slack OAuth refresh error: {error_msg}"
            )

        # Extract bot token from refresh response
        bot_token = None
        if token_json.get("bot") and token_json["bot"].get("bot_access_token"):
            bot_token = token_json["bot"]["bot_access_token"]
        elif token_json.get("access_token"):
            bot_token = token_json["access_token"]
        else:
            raise HTTPException(
                status_code=400, detail="No bot token received from Slack refresh"
            )

        # Get new refresh token if provided (Slack may rotate refresh tokens)
        new_refresh_token = token_json.get("refresh_token")

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        expires_in = token_json.get("expires_in")
        if expires_in:
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(expires_in))

        # Update credentials object with encrypted tokens
        credentials.bot_token = token_encryption.encrypt_token(bot_token)
        if new_refresh_token:
            credentials.refresh_token = token_encryption.encrypt_token(
                new_refresh_token
            )
        credentials.expires_in = expires_in
        credentials.expires_at = expires_at
        credentials.scope = token_json.get("scope")

        # Preserve team info
        if not credentials.team_id:
            credentials.team_id = connector.config.get("team_id")
        if not credentials.team_name:
            credentials.team_name = connector.config.get("team_name")
        if not credentials.bot_user_id:
            credentials.bot_user_id = connector.config.get("bot_user_id")

        # Update connector config with encrypted tokens
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True
        connector.config = credentials_dict
        await session.commit()
        await session.refresh(connector)

        logger.info(f"Successfully refreshed Slack token for connector {connector.id}")

        return connector
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to refresh Slack token for connector {connector.id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Slack token: {e!s}"
        ) from e


@router.get("/slack/connector/{connector_id}/channels")
async def get_slack_channels(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> list[dict[str, Any]]:
    """
    Get list of Slack channels with bot membership status.

    This endpoint fetches all channels the bot can see and indicates
    whether the bot is a member of each channel (required for accessing messages).

    Args:
        connector_id: The Slack connector ID
        session: Database session
        user: Current authenticated user

    Returns:
        List of channels with id, name, is_private, and is_member fields
    """
    try:
        # Get the connector and verify ownership
        result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.SLACK_CONNECTOR,
            )
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="Slack connector not found or access denied",
            )

        # Get credentials and decrypt bot token
        credentials = SlackAuthCredentialsBase.from_dict(connector.config)
        token_encryption = get_token_encryption()
        is_encrypted = connector.config.get("_token_encrypted", False)

        bot_token = credentials.bot_token
        if is_encrypted and bot_token:
            try:
                bot_token = token_encryption.decrypt_token(bot_token)
            except Exception as e:
                logger.error(f"Failed to decrypt bot token: {e!s}")
                raise HTTPException(
                    status_code=500, detail="Failed to decrypt stored bot token"
                ) from e

        if not bot_token:
            raise HTTPException(
                status_code=400,
                detail="No bot token available. Please re-authenticate.",
            )

        # Import SlackHistory here to avoid circular imports
        from app.connectors.slack_history import SlackHistory

        # Create Slack client with direct token (simple pattern for quick operations)
        slack_client = SlackHistory(token=bot_token)

        channels = await slack_client.get_all_channels(include_private=True)

        logger.info(
            f"Fetched {len(channels)} channels for Slack connector {connector_id}"
        )

        return channels

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get Slack channels for connector {connector_id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get Slack channels: {e!s}"
        ) from e
