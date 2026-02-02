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

# Discord permission bits
VIEW_CHANNEL = 1 << 10  # 1024
READ_MESSAGE_HISTORY = 1 << 16  # 65536
ADMINISTRATOR = 1 << 3  # 8

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


def _compute_channel_permissions(
    base_permissions: int,
    bot_role_ids: set[str],
    bot_user_id: str | None,
    channel_overwrites: list[dict],
    guild_id: str,
) -> int:
    """
    Compute effective permissions for a channel based on role permissions and overwrites.

    Discord permission computation follows this order (per official docs):
    1. Start with base permissions from roles
    2. Apply @everyone role overwrites (deny, then allow)
    3. Apply role-specific overwrites (deny, then allow)
    4. Apply member-specific overwrites (deny, then allow)

    Args:
        base_permissions: Combined permissions from all bot roles
        bot_role_ids: Set of role IDs the bot has
        bot_user_id: The bot's user ID for member-specific overwrites
        channel_overwrites: List of permission overwrites for the channel
        guild_id: Guild ID (same as @everyone role ID)

    Returns:
        Computed permission integer
    """
    permissions = base_permissions

    # Permission overwrites are applied in order: @everyone, roles, member
    everyone_allow = 0
    everyone_deny = 0
    role_allow = 0
    role_deny = 0
    member_allow = 0
    member_deny = 0

    for overwrite in channel_overwrites:
        overwrite_id = overwrite.get("id")
        overwrite_type = overwrite.get("type")  # 0 = role, 1 = member
        allow = int(overwrite.get("allow", 0))
        deny = int(overwrite.get("deny", 0))

        if overwrite_type == 0:  # Role overwrite
            if overwrite_id == guild_id:  # @everyone role
                everyone_allow = allow
                everyone_deny = deny
            elif overwrite_id in bot_role_ids:
                role_allow |= allow
                role_deny |= deny
        elif overwrite_type == 1 and bot_user_id and overwrite_id == bot_user_id:
            # Member-specific overwrite for the bot
            member_allow = allow
            member_deny = deny

    # Apply in order per Discord docs:
    # 1. @everyone deny, then allow
    permissions &= ~everyone_deny
    permissions |= everyone_allow
    # 2. Role deny, then allow
    permissions &= ~role_deny
    permissions |= role_allow
    # 3. Member deny, then allow (applied LAST, highest priority)
    permissions &= ~member_deny
    permissions |= member_allow

    return permissions


@router.get("/discord/connector/{connector_id}/channels", response_model=None)
async def get_discord_channels(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get list of Discord text channels for a connector with permission info.

    Uses Discord's HTTP REST API directly instead of WebSocket bot connection.
    Computes effective permissions to determine if bot can read message history.

    Args:
        connector_id: The Discord connector ID
        session: Database session
        user: Current authenticated user

    Returns:
        List of channels with id, name, type, position, category_id, and can_index fields
    """
    from sqlalchemy import select

    try:
        # Get connector and verify ownership
        result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DISCORD_CONNECTOR,
            )
        )
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="Discord connector not found or access denied",
            )

        # Get credentials and decrypt bot token
        credentials = DiscordAuthCredentialsBase.from_dict(connector.config)
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

        # Get guild_id from connector config
        guild_id = connector.config.get("guild_id")
        if not guild_id:
            raise HTTPException(
                status_code=400,
                detail="No guild_id associated with this connector. Please reconnect the Discord server.",
            )

        headers = {"Authorization": f"Bot {bot_token}"}

        async with httpx.AsyncClient() as client:
            # Fetch bot's user info to get bot user ID
            bot_user_response = await client.get(
                "https://discord.com/api/v10/users/@me",
                headers=headers,
                timeout=30.0,
            )

            if bot_user_response.status_code != 200:
                logger.warning(
                    f"Failed to fetch bot user info: {bot_user_response.text}"
                )
                bot_user_id = None
            else:
                bot_user_id = bot_user_response.json().get("id")

            # Fetch guild info to get roles
            guild_response = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_id}",
                headers=headers,
                timeout=30.0,
            )

            if guild_response.status_code != 200:
                raise HTTPException(
                    status_code=guild_response.status_code,
                    detail="Failed to fetch guild information",
                )

            guild_data = guild_response.json()
            guild_roles = {role["id"]: role for role in guild_data.get("roles", [])}

            # Fetch bot's member info to get its roles
            bot_member_response = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_id}/members/{bot_user_id}",
                headers=headers,
                timeout=30.0,
            )

            if bot_member_response.status_code != 200:
                logger.warning(
                    f"Failed to fetch bot member info: {bot_member_response.text}"
                )
                bot_role_ids = {guild_id}  # At minimum, bot has @everyone role
                base_permissions = int(
                    guild_roles.get(guild_id, {}).get("permissions", 0)
                )
            else:
                bot_member_data = bot_member_response.json()
                bot_role_ids = set(bot_member_data.get("roles", []))
                bot_role_ids.add(guild_id)  # @everyone role is always included

                # Compute base permissions from all bot roles
                base_permissions = 0
                for role_id in bot_role_ids:
                    if role_id in guild_roles:
                        role_perms = int(guild_roles[role_id].get("permissions", 0))
                        base_permissions |= role_perms

            # Check if bot has administrator permission (bypasses all checks)
            is_admin = (base_permissions & ADMINISTRATOR) == ADMINISTRATOR

            # Fetch channels
            channels_response = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_id}/channels",
                headers=headers,
                timeout=30.0,
            )

        if channels_response.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail="Bot does not have permission to view channels in this server. Please ensure the bot has the 'View Channels' permission.",
            )
        elif channels_response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Discord server not found. The bot may have been removed from the server.",
            )
        elif channels_response.status_code != 200:
            error_detail = channels_response.text
            try:
                error_json = channels_response.json()
                error_detail = error_json.get("message", error_detail)
            except Exception:
                pass
            raise HTTPException(
                status_code=channels_response.status_code,
                detail=f"Failed to fetch Discord channels: {error_detail}",
            )

        channels_data = channels_response.json()

        # Discord channel types:
        # 0 = GUILD_TEXT, 2 = GUILD_VOICE, 4 = GUILD_CATEGORY, 5 = GUILD_ANNOUNCEMENT
        # We want text channels (type 0) and announcement channels (type 5)
        text_channel_types = {0, 5}

        text_channels = []
        for ch in channels_data:
            if ch.get("type") in text_channel_types:
                # Compute effective permissions for this channel
                if is_admin:
                    # Administrators bypass all permission checks
                    can_index = True
                else:
                    channel_overwrites = ch.get("permission_overwrites", [])
                    effective_perms = _compute_channel_permissions(
                        base_permissions,
                        bot_role_ids,
                        bot_user_id,
                        channel_overwrites,
                        guild_id,
                    )

                    # Bot can index if it has both VIEW_CHANNEL and READ_MESSAGE_HISTORY
                    has_view = (effective_perms & VIEW_CHANNEL) == VIEW_CHANNEL
                    has_read_history = (
                        effective_perms & READ_MESSAGE_HISTORY
                    ) == READ_MESSAGE_HISTORY
                    can_index = has_view and has_read_history

                text_channels.append(
                    {
                        "id": ch["id"],
                        "name": ch["name"],
                        "type": "text" if ch["type"] == 0 else "announcement",
                        "position": ch.get("position", 0),
                        "category_id": ch.get("parent_id"),
                        "can_index": can_index,
                    }
                )

        # Sort by position
        text_channels.sort(key=lambda x: x["position"])

        logger.info(
            f"Fetched {len(text_channels)} text channels for Discord connector {connector_id}"
        )

        return text_channels

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get Discord channels for connector {connector_id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get Discord channels: {e!s}"
        ) from e
