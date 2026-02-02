"""
Confluence Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Confluence connector.
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
from app.schemas.atlassian_auth_credentials import AtlassianAuthCredentialsBase
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    extract_identifier_from_credentials,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

# Atlassian OAuth endpoints
AUTHORIZATION_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

# OAuth scopes for Confluence
SCOPES = [
    "read:confluence-user",
    "read:space:confluence",
    "read:page:confluence",
    "read:comment:confluence",
    "offline_access",  # Required for refresh tokens
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


@router.get("/auth/confluence/connector/add")
async def connect_confluence(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Confluence OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.ATLASSIAN_CLIENT_ID:
            raise HTTPException(
                status_code=500, detail="Atlassian OAuth not configured."
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
            "audience": "api.atlassian.com",
            "client_id": config.ATLASSIAN_CLIENT_ID,
            "scope": " ".join(SCOPES),
            "redirect_uri": config.CONFLUENCE_REDIRECT_URI,
            "state": state_encoded,
            "response_type": "code",
            "prompt": "consent",
        }

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(
            f"Generated Confluence OAuth URL for user {user.id}, space {space_id}"
        )
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate Confluence OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Confluence OAuth: {e!s}"
        ) from e


@router.get("/auth/confluence/connector/callback")
async def confluence_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Confluence OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from Atlassian (if user granted access)
        error: Error code from Atlassian (if user denied access or error occurred)
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Confluence OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=confluence_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=confluence_oauth_denied"
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
        if not config.CONFLUENCE_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="CONFLUENCE_REDIRECT_URI not configured"
            )

        # Exchange authorization code for access token
        token_data = {
            "grant_type": "authorization_code",
            "client_id": config.ATLASSIAN_CLIENT_ID,
            "client_secret": config.ATLASSIAN_CLIENT_SECRET,
            "code": code,
            "redirect_uri": config.CONFLUENCE_REDIRECT_URI,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                json=token_data,
                headers={"Content-Type": "application/json"},
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

        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")
        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Atlassian"
            )

        # Get accessible resources to find Confluence cloud ID and site URL
        async with httpx.AsyncClient() as client:
            resources_response = await client.get(
                RESOURCES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

        cloud_id = None
        site_url = None
        if resources_response.status_code == 200:
            resources = resources_response.json()
            # Find Confluence resource
            for resource in resources:
                if resource.get("id") and resource.get("name"):
                    cloud_id = resource.get("id")
                    site_url = resource.get("url")
                    break

        if not cloud_id:
            logger.warning(
                "Could not determine Confluence cloud ID from accessible resources"
            )

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        expires_in = token_json.get("expires_in")
        if expires_in:
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(expires_in))

        # Encrypt sensitive tokens before storing
        token_encryption = get_token_encryption()

        # Store the encrypted tokens and metadata in connector config
        connector_config = {
            "access_token": token_encryption.encrypt_token(access_token),
            "refresh_token": token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            "token_type": token_json.get("token_type", "Bearer"),
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": token_json.get("scope"),
            "cloud_id": cloud_id,
            "base_url": site_url,  # Store as base_url to match shared schema
            # Mark that tokens are encrypted for backward compatibility
            "_token_encrypted": True,
        }

        # Extract unique identifier from connector credentials
        connector_identifier = extract_identifier_from_credentials(
            SearchSourceConnectorType.CONFLUENCE_CONNECTOR, connector_config
        )

        # Check for duplicate connector (same Confluence instance already connected)
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Confluence connector detected for user {user_id} with instance {connector_identifier}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=confluence-connector"
            )

        # Generate a unique, user-friendly connector name
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )
        # Create new connector
        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
            is_indexable=True,
            config=connector_config,
            search_space_id=space_id,
            user_id=user_id,
        )
        session.add(new_connector)
        logger.info(
            f"Created new Confluence connector for user {user_id} in space {space_id}"
        )

        try:
            await session.commit()
            logger.info(f"Successfully saved Confluence connector for user {user_id}")

            # Redirect to the frontend with success params
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=confluence-connector&connectorId={new_connector.id}"
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
        logger.error(f"Failed to complete Confluence OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Confluence OAuth: {e!s}"
        ) from e


async def refresh_confluence_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
    """
    Refresh the Confluence access token for a connector.

    Args:
        session: Database session
        connector: Confluence connector to refresh

    Returns:
        Updated connector object
    """
    try:
        logger.info(f"Refreshing Confluence token for connector {connector.id}")

        credentials = AtlassianAuthCredentialsBase.from_dict(connector.config)

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

        # Prepare token refresh data
        refresh_data = {
            "grant_type": "refresh_token",
            "client_id": config.ATLASSIAN_CLIENT_ID,
            "client_secret": config.ATLASSIAN_CLIENT_SECRET,
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                json=refresh_data,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )

        if token_response.status_code != 200:
            error_detail = token_response.text
            error_code = ""
            try:
                error_json = token_response.json()
                error_detail = error_json.get(
                    "error_description", error_json.get("error", error_detail)
                )
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
                    detail="Confluence authentication failed. Please re-authenticate.",
                )
            raise HTTPException(
                status_code=400, detail=f"Token refresh failed: {error_detail}"
            )

        token_json = token_response.json()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        expires_in = token_json.get("expires_in")
        if expires_in:
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(expires_in))

        # Encrypt new tokens before storing
        access_token = token_json.get("access_token")
        new_refresh_token = token_json.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="No access token received from Confluence refresh",
            )

        # Update credentials object with encrypted tokens
        credentials.access_token = token_encryption.encrypt_token(access_token)
        if new_refresh_token:
            credentials.refresh_token = token_encryption.encrypt_token(
                new_refresh_token
            )
        credentials.expires_in = expires_in
        credentials.expires_at = expires_at
        credentials.scope = token_json.get("scope")

        # Preserve cloud_id and base_url (with backward compatibility for site_url)
        if not credentials.cloud_id:
            credentials.cloud_id = connector.config.get("cloud_id")
        if not credentials.base_url:
            # Check both base_url and site_url for backward compatibility
            credentials.base_url = connector.config.get(
                "base_url"
            ) or connector.config.get("site_url")

        # Update connector config with encrypted tokens
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True
        connector.config = credentials_dict
        await session.commit()
        await session.refresh(connector)

        logger.info(
            f"Successfully refreshed Confluence token for connector {connector.id}"
        )

        return connector
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh Confluence token: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Confluence token: {e!s}"
        ) from e
