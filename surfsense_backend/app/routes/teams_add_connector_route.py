"""
Microsoft Teams Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Microsoft Teams connector using Microsoft Graph API.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.schemas.teams_auth_credentials import TeamsAuthCredentialsBase
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    extract_identifier_from_credentials,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

# Microsoft identity platform endpoints
AUTHORIZATION_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

# OAuth scopes for Microsoft Teams (Graph API)
SCOPES = [
    "offline_access",  # Required for refresh tokens
    "User.Read",  # Read user profile
    "Team.ReadBasic.All",  # Read basic team information
    "Channel.ReadBasic.All",  # Read basic channel information
    "ChannelMessage.Read.All",  # Read messages in channels
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


@router.get("/auth/teams/connector/add")
async def connect_teams(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Microsoft Teams OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.TEAMS_CLIENT_ID:
            raise HTTPException(
                status_code=500, detail="Microsoft Teams OAuth not configured."
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
            "client_id": config.TEAMS_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": config.TEAMS_REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(SCOPES),
            "state": state_encoded,
        }

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(
            "Generated Microsoft Teams OAuth URL for user %s, space %s",
            user.id,
            space_id,
        )
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(
            "Failed to initiate Microsoft Teams OAuth: %s", str(e), exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate Microsoft Teams OAuth: {e!s}",
        ) from e


@router.get("/auth/teams/connector/callback")
async def teams_callback(
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Microsoft Teams OAuth callback.

    Args:
        code: Authorization code from Microsoft (if user granted access)
        error: Error code from Microsoft (if user denied access or error occurred)
        error_description: Human-readable error description
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            error_msg = error_description or error
            logger.warning("Microsoft Teams OAuth error: %s", error_msg)
            redirect_url = f"{config.NEXT_FRONTEND_URL}/dashboard?error=teams_auth_failed&message={error_msg}"
            return RedirectResponse(url=redirect_url)

        # Validate required parameters
        if not code or not state:
            raise HTTPException(
                status_code=400, detail="Missing required OAuth parameters"
            )

        # Verify and decode state parameter
        state_manager = get_state_manager()
        try:
            data = state_manager.validate_state(state)
            space_id = data["space_id"]
            user_id = UUID(data["user_id"])
        except (HTTPException, ValueError, KeyError) as e:
            logger.error("Invalid OAuth state: %s", str(e))
            redirect_url = f"{config.NEXT_FRONTEND_URL}/dashboard?error=invalid_state"
            return RedirectResponse(url=redirect_url)

        # Exchange authorization code for access token
        token_data = {
            "client_id": config.TEAMS_CLIENT_ID,
            "client_secret": config.TEAMS_CLIENT_SECRET,
            "code": code,
            "redirect_uri": config.TEAMS_REDIRECT_URI,
            "grant_type": "authorization_code",
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
                error_detail = error_json.get("error_description", error_detail)
            except Exception:
                pass
            raise HTTPException(
                status_code=400, detail=f"Token exchange failed: {error_detail}"
            )

        token_json = token_response.json()

        # Extract tokens from response
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Microsoft"
            )

        # Encrypt sensitive tokens before storing
        token_encryption = get_token_encryption()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Fetch user info from Microsoft Graph API
        user_info = {}
        tenant_info = {}
        try:
            async with httpx.AsyncClient() as client:
                # Get user profile
                user_response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    user_info = {
                        "user_id": user_data.get("id"),
                        "user_name": user_data.get("displayName"),
                        "user_email": user_data.get("mail")
                        or user_data.get("userPrincipalName"),
                    }

                # Get organization/tenant info
                org_response = await client.get(
                    "https://graph.microsoft.com/v1.0/organization",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                if org_response.status_code == 200:
                    org_data = org_response.json()
                    if org_data.get("value") and len(org_data["value"]) > 0:
                        org = org_data["value"][0]
                        tenant_info = {
                            "tenant_id": org.get("id"),
                            "tenant_name": org.get("displayName"),
                        }
        except Exception as e:
            logger.warning(
                "Failed to fetch user/tenant info from Microsoft Graph: %s", str(e)
            )

        # Store the encrypted tokens and user/tenant info in connector config
        connector_config = {
            "access_token": token_encryption.encrypt_token(access_token),
            "refresh_token": token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            "token_type": token_json.get("token_type", "Bearer"),
            "expires_in": token_json.get("expires_in"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": token_json.get("scope"),
            "tenant_id": tenant_info.get("tenant_id"),
            "tenant_name": tenant_info.get("tenant_name"),
            "user_id": user_info.get("user_id"),
            # Mark that token is encrypted for backward compatibility
            "_token_encrypted": True,
        }

        # Extract unique identifier from connector credentials
        connector_identifier = extract_identifier_from_credentials(
            SearchSourceConnectorType.TEAMS_CONNECTOR, connector_config
        )

        # Check for duplicate connector (same tenant already connected)
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.TEAMS_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )

        if is_duplicate:
            logger.warning(
                "Duplicate Microsoft Teams connector for user %s, space %s, tenant %s",
                user_id,
                space_id,
                tenant_info.get("tenant_name"),
            )
            redirect_url = f"{config.NEXT_FRONTEND_URL}/dashboard?error=duplicate_connector&message=This Microsoft Teams tenant is already connected to this space"
            return RedirectResponse(url=redirect_url)

        # Generate unique connector name
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.TEAMS_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )

        # Create new connector
        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.TEAMS_CONNECTOR,
            is_indexable=True,
            config=connector_config,
            search_space_id=space_id,
            user_id=user_id,
        )

        try:
            session.add(new_connector)
            await session.commit()
            await session.refresh(new_connector)

            logger.info(
                "Successfully created Microsoft Teams connector %s for user %s",
                new_connector.id,
                user_id,
            )

            # Redirect to frontend with success
            redirect_url = f"{config.NEXT_FRONTEND_URL}/dashboard?success=teams_connected&connector_id={new_connector.id}"
            return RedirectResponse(url=redirect_url)

        except IntegrityError as e:
            await session.rollback()
            logger.error(
                "Database integrity error creating Teams connector: %s", str(e)
            )
            redirect_url = (
                f"{config.NEXT_FRONTEND_URL}/dashboard?error=connector_creation_failed"
            )
            return RedirectResponse(url=redirect_url)

    except HTTPException:
        raise
    except (IntegrityError, ValueError) as e:
        logger.error("Teams OAuth callback error: %s", str(e), exc_info=True)
        redirect_url = f"{config.NEXT_FRONTEND_URL}/dashboard?error=teams_auth_error"
        return RedirectResponse(url=redirect_url)


async def refresh_teams_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
    """
    Refresh Microsoft Teams OAuth tokens.

    Args:
        session: Database session
        connector: The connector to refresh

    Returns:
        Updated connector with refreshed tokens

    Raises:
        HTTPException: If token refresh fails
    """
    logger.info(
        "Refreshing Microsoft Teams OAuth tokens for connector %s", connector.id
    )

    credentials = TeamsAuthCredentialsBase.from_dict(connector.config)

    # Decrypt tokens if they are encrypted
    token_encryption = get_token_encryption()
    is_encrypted = connector.config.get("_token_encrypted", False)
    refresh_token = credentials.refresh_token

    if is_encrypted and refresh_token:
        try:
            refresh_token = token_encryption.decrypt_token(refresh_token)
        except Exception as e:
            logger.error("Failed to decrypt refresh token: %s", str(e))
            raise HTTPException(
                status_code=500, detail="Failed to decrypt stored refresh token"
            ) from e

    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail=f"No refresh token available for connector {connector.id}",
        )

    # Microsoft uses oauth2/v2.0/token for token refresh
    refresh_data = {
        "client_id": config.TEAMS_CLIENT_ID,
        "client_secret": config.TEAMS_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": " ".join(SCOPES),
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
        error_code = ""
        try:
            error_json = token_response.json()
            error_detail = error_json.get("error_description", error_detail)
            error_code = error_json.get("error", "")
        except Exception:
            pass
        # Check if this is a token expiration/revocation error
        error_lower = (error_detail + error_code).lower()
        if (
            "invalid_grant" in error_lower
            or "expired" in error_lower
            or "revoked" in error_lower
        ):
            raise HTTPException(
                status_code=401,
                detail="Microsoft Teams authentication failed. Please re-authenticate.",
            )
        raise HTTPException(
            status_code=400, detail=f"Token refresh failed: {error_detail}"
        )

    token_json = token_response.json()

    # Extract new tokens
    access_token = token_json.get("access_token")
    new_refresh_token = token_json.get("refresh_token")

    if not access_token:
        raise HTTPException(
            status_code=400, detail="No access token received from Microsoft refresh"
        )

    # Calculate expiration time (UTC, tz-aware)
    expires_at = None
    expires_in = token_json.get("expires_in")
    if expires_in:
        now_utc = datetime.now(UTC)
        expires_at = now_utc + timedelta(seconds=int(expires_in))

    # Update credentials object with encrypted tokens
    credentials.access_token = token_encryption.encrypt_token(access_token)
    if new_refresh_token:
        credentials.refresh_token = token_encryption.encrypt_token(new_refresh_token)
    credentials.expires_in = expires_in
    credentials.expires_at = expires_at
    credentials.scope = token_json.get("scope")

    # Preserve tenant/user info
    if not credentials.tenant_id:
        credentials.tenant_id = connector.config.get("tenant_id")
    if not credentials.tenant_name:
        credentials.tenant_name = connector.config.get("tenant_name")
    if not credentials.user_id:
        credentials.user_id = connector.config.get("user_id")

    # Update connector config with encrypted tokens
    credentials_dict = credentials.to_dict()
    credentials_dict["_token_encrypted"] = True
    connector.config = credentials_dict

    await session.commit()
    await session.refresh(connector)

    logger.info(
        "Successfully refreshed Microsoft Teams tokens for connector %s", connector.id
    )

    return connector
