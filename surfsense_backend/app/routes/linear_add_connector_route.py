"""
Linear Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Linear connector.
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
from app.connectors.linear_connector import fetch_linear_organization_name
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.schemas.linear_auth_credentials import LinearAuthCredentialsBase
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

# Linear OAuth endpoints
AUTHORIZATION_URL = "https://linear.app/oauth/authorize"
TOKEN_URL = "https://api.linear.app/oauth/token"

# OAuth scopes for Linear
SCOPES = ["read", "write"]

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


def make_basic_auth_header(client_id: str, client_secret: str) -> str:
    """Create Basic Auth header for Linear OAuth."""
    import base64

    credentials = f"{client_id}:{client_secret}".encode()
    b64 = base64.b64encode(credentials).decode("ascii")
    return f"Basic {b64}"


@router.get("/auth/linear/connector/add")
async def connect_linear(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Linear OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.LINEAR_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Linear OAuth not configured.")

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
            "client_id": config.LINEAR_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": config.LINEAR_REDIRECT_URI,
            "scope": " ".join(SCOPES),
            "state": state_encoded,
        }

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(f"Generated Linear OAuth URL for user {user.id}, space {space_id}")
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate Linear OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Linear OAuth: {e!s}"
        ) from e


@router.get("/auth/linear/connector/callback")
async def linear_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Linear OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from Linear (if user granted access)
        error: Error code from Linear (if user denied access or error occurred)
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Linear OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=linear_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=linear_oauth_denied"
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
        if not config.LINEAR_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="LINEAR_REDIRECT_URI not configured"
            )

        # Exchange authorization code for access token
        auth_header = make_basic_auth_header(
            config.LINEAR_CLIENT_ID, config.LINEAR_CLIENT_SECRET
        )

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.LINEAR_REDIRECT_URI,  # Use stored value, not from request
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                data=token_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": auth_header,
                },
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

        # Encrypt sensitive tokens before storing
        token_encryption = get_token_encryption()
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Linear"
            )

        # Fetch organization name
        org_name = await fetch_linear_organization_name(access_token)

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Store the encrypted access token and refresh token in connector config
        connector_config = {
            "access_token": token_encryption.encrypt_token(access_token),
            "refresh_token": token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            "token_type": token_json.get("token_type", "Bearer"),
            "expires_in": token_json.get("expires_in"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": token_json.get("scope"),
            # Mark that tokens are encrypted for backward compatibility
            "_token_encrypted": True,
        }

        # Check for duplicate connector (same organization already connected)
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.LINEAR_CONNECTOR,
            space_id,
            user_id,
            org_name,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Linear connector detected for user {user_id} with org {org_name}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=linear-connector"
            )

        # Generate a unique, user-friendly connector name
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.LINEAR_CONNECTOR,
            space_id,
            user_id,
            org_name,
        )
        # Create new connector
        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.LINEAR_CONNECTOR,
            is_indexable=True,
            config=connector_config,
            search_space_id=space_id,
            user_id=user_id,
        )
        session.add(new_connector)
        logger.info(
            f"Created new Linear connector for user {user_id} in space {space_id}"
        )

        try:
            await session.commit()
            logger.info(f"Successfully saved Linear connector for user {user_id}")

            # Redirect to the frontend with success params
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=linear-connector&connectorId={new_connector.id}"
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
        logger.error(f"Failed to complete Linear OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Linear OAuth: {e!s}"
        ) from e


async def refresh_linear_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
    """
    Refresh the Linear access token for a connector.

    Args:
        session: Database session
        connector: Linear connector to refresh

    Returns:
        Updated connector object
    """
    try:
        logger.info(f"Refreshing Linear token for connector {connector.id}")

        credentials = LinearAuthCredentialsBase.from_dict(connector.config)

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

        auth_header = make_basic_auth_header(
            config.LINEAR_CLIENT_ID, config.LINEAR_CLIENT_SECRET
        )

        # Prepare token refresh data
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                data=refresh_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": auth_header,
                },
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
                    detail="Linear authentication failed. Please re-authenticate.",
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
                status_code=400, detail="No access token received from Linear refresh"
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

        # Update connector config with encrypted tokens
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True
        connector.config = credentials_dict
        await session.commit()
        await session.refresh(connector)

        logger.info(f"Successfully refreshed Linear token for connector {connector.id}")

        return connector
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh Linear token: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Linear token: {e!s}"
        ) from e
