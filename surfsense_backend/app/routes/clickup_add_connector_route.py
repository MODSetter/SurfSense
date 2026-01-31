"""
ClickUp Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for ClickUp connector.
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
from sqlalchemy.future import select

from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.schemas.clickup_auth_credentials import ClickUpAuthCredentialsBase
from app.users import current_active_user
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

# ClickUp OAuth endpoints
AUTHORIZATION_URL = "https://app.clickup.com/api"
TOKEN_URL = "https://api.clickup.com/api/v2/oauth/token"

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


@router.get("/auth/clickup/connector/add")
async def connect_clickup(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate ClickUp OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.CLICKUP_CLIENT_ID:
            raise HTTPException(status_code=500, detail="ClickUp OAuth not configured.")

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
            "client_id": config.CLICKUP_CLIENT_ID,
            "redirect_uri": config.CLICKUP_REDIRECT_URI,
            "state": state_encoded,
        }

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(f"Generated ClickUp OAuth URL for user {user.id}, space {space_id}")
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate ClickUp OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate ClickUp OAuth: {e!s}"
        ) from e


@router.get("/auth/clickup/connector/callback")
async def clickup_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle ClickUp OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from ClickUp (if user granted access)
        error: Error code from ClickUp (if user denied access or error occurred)
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"ClickUp OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=clickup_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=clickup_oauth_denied"
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
        if not config.CLICKUP_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="CLICKUP_REDIRECT_URI not configured"
            )

        # Exchange authorization code for access token
        token_data = {
            "client_id": config.CLICKUP_CLIENT_ID,
            "client_secret": config.CLICKUP_CLIENT_SECRET,
            "code": code,
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
                error_detail = error_json.get("error", error_detail)
            except Exception:
                pass
            raise HTTPException(
                status_code=400, detail=f"Token exchange failed: {error_detail}"
            )

        token_json = token_response.json()

        # Extract access token
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from ClickUp"
            )

        # Extract refresh token if available
        refresh_token = token_json.get("refresh_token")

        # Encrypt sensitive tokens before storing
        token_encryption = get_token_encryption()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        expires_in = token_json.get("expires_in")
        if expires_in:
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(expires_in))

        # Get user information and workspace information from ClickUp API
        user_info = {}
        workspace_info = {}
        try:
            async with httpx.AsyncClient() as client:
                # Get user info
                user_response = await client.get(
                    "https://api.clickup.com/api/v2/user",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                if user_response.status_code == 200:
                    user_data = user_response.json().get("user", {})
                    user_info = {
                        "user_id": str(user_data.get("id"))
                        if user_data.get("id") is not None
                        else None,
                        "user_email": user_data.get("email"),
                        "user_name": user_data.get("username"),
                    }

                # Get workspace (team) info - get the first workspace
                team_response = await client.get(
                    "https://api.clickup.com/api/v2/team",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                if team_response.status_code == 200:
                    teams_data = team_response.json().get("teams", [])
                    if teams_data and len(teams_data) > 0:
                        first_team = teams_data[0]
                        workspace_info = {
                            "workspace_id": str(first_team.get("id"))
                            if first_team.get("id") is not None
                            else None,
                            "workspace_name": first_team.get("name"),
                        }
        except Exception as e:
            logger.warning(f"Failed to fetch user/workspace info from ClickUp: {e!s}")

        # Store the encrypted tokens and user/workspace info in connector config
        connector_config = {
            "access_token": token_encryption.encrypt_token(access_token),
            "refresh_token": token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "user_id": user_info.get("user_id"),
            "user_email": user_info.get("user_email"),
            "user_name": user_info.get("user_name"),
            "workspace_id": workspace_info.get("workspace_id"),
            "workspace_name": workspace_info.get("workspace_name"),
            # Mark that token is encrypted for backward compatibility
            "_token_encrypted": True,
        }

        # Check if connector already exists for this search space and user
        existing_connector_result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.CLICKUP_CONNECTOR,
            )
        )
        existing_connector = existing_connector_result.scalars().first()

        if existing_connector:
            # Update existing connector
            existing_connector.config = connector_config
            existing_connector.name = "ClickUp Connector"
            existing_connector.is_indexable = True
            logger.info(
                f"Updated existing ClickUp connector for user {user_id} in space {space_id}"
            )
        else:
            # Create new connector
            new_connector = SearchSourceConnector(
                name="ClickUp Connector",
                connector_type=SearchSourceConnectorType.CLICKUP_CONNECTOR,
                is_indexable=True,
                config=connector_config,
                search_space_id=space_id,
                user_id=user_id,
            )
            session.add(new_connector)
            logger.info(
                f"Created new ClickUp connector for user {user_id} in space {space_id}"
            )

        try:
            await session.commit()
            logger.info(f"Successfully saved ClickUp connector for user {user_id}")

            # Redirect to the frontend with success params
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=clickup-connector"
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
                detail=f"Integrity error: A connector with this type already exists. {e!s}",
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
        logger.error(f"Failed to complete ClickUp OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete ClickUp OAuth: {e!s}"
        ) from e


async def refresh_clickup_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
    """
    Refresh the ClickUp access token for a connector.

    Args:
        session: Database session
        connector: ClickUp connector to refresh

    Returns:
        Updated connector object
    """
    try:
        logger.info(f"Refreshing ClickUp token for connector {connector.id}")

        credentials = ClickUpAuthCredentialsBase.from_dict(connector.config)

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
            "client_id": config.CLICKUP_CLIENT_ID,
            "client_secret": config.CLICKUP_CLIENT_SECRET,
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
            try:
                error_json = token_response.json()
                error_detail = error_json.get("error", error_detail)
            except Exception:
                pass
            # Check if this is a token expiration/revocation error
            error_lower = error_detail.lower()
            if (
                "invalid_grant" in error_lower
                or "expired" in error_lower
                or "revoked" in error_lower
            ):
                raise HTTPException(
                    status_code=401,
                    detail="ClickUp authentication failed. Please re-authenticate.",
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
                status_code=400, detail="No access token received from ClickUp refresh"
            )

        # Update credentials object with encrypted tokens
        credentials.access_token = token_encryption.encrypt_token(access_token)
        if new_refresh_token:
            credentials.refresh_token = token_encryption.encrypt_token(
                new_refresh_token
            )
        credentials.expires_in = expires_in
        credentials.expires_at = expires_at

        # Preserve user and workspace info
        if not credentials.user_id:
            credentials.user_id = connector.config.get("user_id")
        if not credentials.user_email:
            credentials.user_email = connector.config.get("user_email")
        if not credentials.user_name:
            credentials.user_name = connector.config.get("user_name")
        if not credentials.workspace_id:
            credentials.workspace_id = connector.config.get("workspace_id")
        if not credentials.workspace_name:
            credentials.workspace_name = connector.config.get("workspace_name")

        # Update connector config with encrypted tokens
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True
        connector.config = credentials_dict
        await session.commit()
        await session.refresh(connector)

        logger.info(
            f"Successfully refreshed ClickUp token for connector {connector.id}"
        )

        return connector
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh ClickUp token: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh ClickUp token: {e!s}"
        ) from e
