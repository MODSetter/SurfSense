"""
Discord Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Discord connector.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.schemas.discord_auth_credentials import DiscordAuthCredentialsBase
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    extract_identifier_from_credentials,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

# Discord OAuth endpoints
AUTHORIZATION_URL = "https://discord.com/api/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"

# OAuth scopes for Discord (Bot Token)
SCOPES = [
    "bot",  # Basic bot scope
    "guilds",  # Access to guild information
    "guilds.members.read",  # Read member information
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


@router.get("/auth/discord/connector/add")
async def connect_discord(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Discord OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.DISCORD_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Discord OAuth not configured.")

        if not config.DISCORD_BOT_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="Discord bot token not configured. Please set DISCORD_BOT_TOKEN in backend configuration.",
            )

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
            "client_id": config.DISCORD_CLIENT_ID,
            "scope": " ".join(SCOPES),  # Discord uses space-separated scopes
            "redirect_uri": config.DISCORD_REDIRECT_URI,
            "response_type": "code",
            "state": state_encoded,
        }

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(f"Generated Discord OAuth URL for user {user.id}, space {space_id}")
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate Discord OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Discord OAuth: {e!s}"
        ) from e


@router.get("/auth/discord/connector/callback")
async def discord_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Discord OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from Discord (if user granted access)
        error: Error code from Discord (if user denied access or error occurred)
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Discord OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=discord_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=discord_oauth_denied"
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
        if not config.DISCORD_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="DISCORD_REDIRECT_URI not configured"
            )

        # Exchange authorization code for access token
        token_data = {
            "client_id": config.DISCORD_CLIENT_ID,
            "client_secret": config.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.DISCORD_REDIRECT_URI,
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
                error_detail = error_json.get(
                    "error_description", error_json.get("error", error_detail)
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=400, detail=f"Token exchange failed: {error_detail}"
            )

        token_json = token_response.json()

        # Log OAuth response for debugging (without sensitive data)
        logger.info(f"Discord OAuth response received. Keys: {list(token_json.keys())}")

        # Discord OAuth with 'bot' scope returns access_token (user token), not bot token
        # The bot token must come from backend config (DISCORD_BOT_TOKEN)
        # OAuth is used to authorize bot installation to servers, not to get bot token
        if not config.DISCORD_BOT_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="Discord bot token not configured. Please set DISCORD_BOT_TOKEN in backend configuration.",
            )

        # Use the bot token from backend config (not the OAuth access_token)
        bot_token = config.DISCORD_BOT_TOKEN

        # Extract OAuth access_token and refresh_token (for reference, not used for bot operations)
        oauth_access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

        # Encrypt sensitive tokens before storing
        token_encryption = get_token_encryption()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Extract guild info from OAuth response if available
        guild_id = None
        guild_name = None
        if token_json.get("guild"):
            guild_id = token_json["guild"].get("id")
            guild_name = token_json["guild"].get("name")

        # Store the bot token from config and OAuth metadata
        connector_config = {
            "bot_token": token_encryption.encrypt_token(
                bot_token
            ),  # Use bot token from config
            "oauth_access_token": token_encryption.encrypt_token(oauth_access_token)
            if oauth_access_token
            else None,  # Store OAuth token for reference
            "refresh_token": token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            "token_type": token_json.get("token_type", "Bearer"),
            "expires_in": token_json.get("expires_in"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": token_json.get("scope"),
            "guild_id": guild_id,
            "guild_name": guild_name,
            # Mark that tokens are encrypted for backward compatibility
            "_token_encrypted": True,
        }

        # Extract unique identifier from connector credentials
        connector_identifier = extract_identifier_from_credentials(
            SearchSourceConnectorType.DISCORD_CONNECTOR, connector_config
        )

        # Check for duplicate connector (same server already connected)
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.DISCORD_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Discord connector detected for user {user_id} with server {connector_identifier}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=discord-connector"
            )

        # Generate a unique, user-friendly connector name
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.DISCORD_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )
        # Create new connector
        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.DISCORD_CONNECTOR,
            is_indexable=True,
            config=connector_config,
            search_space_id=space_id,
            user_id=user_id,
        )
        session.add(new_connector)
        logger.info(
            f"Created new Discord connector for user {user_id} in space {space_id}"
        )

        try:
            await session.commit()
            logger.info(f"Successfully saved Discord connector for user {user_id}")

            # Redirect to the frontend with success params
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=discord-connector&connectorId={new_connector.id}"
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
        logger.error(f"Failed to complete Discord OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Discord OAuth: {e!s}"
        ) from e


async def refresh_discord_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
    """
    Refresh the Discord OAuth tokens for a connector.

    Note: Bot tokens from config don't expire, but OAuth access tokens might.
    This function refreshes OAuth tokens if needed, but always uses bot token from config.

    Args:
        session: Database session
        connector: Discord connector to refresh

    Returns:
        Updated connector object
    """
    try:
        logger.info(f"Refreshing Discord OAuth tokens for connector {connector.id}")

        # Bot token always comes from config, not from OAuth
        if not config.DISCORD_BOT_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="Discord bot token not configured. Please set DISCORD_BOT_TOKEN in backend configuration.",
            )

        credentials = DiscordAuthCredentialsBase.from_dict(connector.config)

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

        # If no refresh token, bot token from config is still valid (bot tokens don't expire)
        # Just update the bot token from config in case it was changed
        if not refresh_token:
            logger.info(
                f"No refresh token available for connector {connector.id}. Using bot token from config."
            )
            # Update bot token from config (in case it was changed)
            credentials.bot_token = token_encryption.encrypt_token(
                config.DISCORD_BOT_TOKEN
            )
            credentials_dict = credentials.to_dict()
            credentials_dict["_token_encrypted"] = True
            connector.config = credentials_dict
            await session.commit()
            await session.refresh(connector)
            return connector

        # Discord uses oauth2/token for token refresh with grant_type=refresh_token
        refresh_data = {
            "client_id": config.DISCORD_CLIENT_ID,
            "client_secret": config.DISCORD_CLIENT_SECRET,
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
                error_detail = error_json.get(
                    "error_description", error_json.get("error", error_detail)
                )
            except Exception:
                pass
            # If refresh fails, bot token from config is still valid
            logger.warning(
                f"OAuth token refresh failed for connector {connector.id}: {error_detail}. "
                "Using bot token from config."
            )
            # Update bot token from config
            credentials.bot_token = token_encryption.encrypt_token(
                config.DISCORD_BOT_TOKEN
            )
            credentials.refresh_token = None  # Clear invalid refresh token
            credentials_dict = credentials.to_dict()
            credentials_dict["_token_encrypted"] = True
            connector.config = credentials_dict
            await session.commit()
            await session.refresh(connector)
            return connector

        token_json = token_response.json()

        # Extract OAuth access token from refresh response (for reference)
        oauth_access_token = token_json.get("access_token")

        # Get new refresh token if provided (Discord may rotate refresh tokens)
        new_refresh_token = token_json.get("refresh_token")

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        expires_in = token_json.get("expires_in")
        if expires_in:
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(expires_in))

        # Always use bot token from config (bot tokens don't expire)
        credentials.bot_token = token_encryption.encrypt_token(config.DISCORD_BOT_TOKEN)

        # Update OAuth tokens if available
        if oauth_access_token:
            # Store OAuth access token for reference
            connector.config["oauth_access_token"] = token_encryption.encrypt_token(
                oauth_access_token
            )
        if new_refresh_token:
            credentials.refresh_token = token_encryption.encrypt_token(
                new_refresh_token
            )
        credentials.expires_in = expires_in
        credentials.expires_at = expires_at
        credentials.scope = token_json.get("scope")

        # Preserve guild info if present
        if not credentials.guild_id:
            credentials.guild_id = connector.config.get("guild_id")
        if not credentials.guild_name:
            credentials.guild_name = connector.config.get("guild_name")
        if not credentials.bot_user_id:
            credentials.bot_user_id = connector.config.get("bot_user_id")

        # Update connector config with encrypted tokens
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True
        connector.config = credentials_dict
        await session.commit()
        await session.refresh(connector)

        logger.info(
            f"Successfully refreshed Discord OAuth tokens for connector {connector.id}"
        )

        return connector
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to refresh Discord tokens for connector {connector.id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Discord tokens: {e!s}"
        ) from e
