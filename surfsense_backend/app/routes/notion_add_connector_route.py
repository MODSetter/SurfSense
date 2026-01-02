"""
Notion Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Notion connector.
"""

import json
import logging
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
from app.users import current_active_user
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

# Notion OAuth endpoints
AUTHORIZATION_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"

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
    """Create Basic Auth header for Notion OAuth."""
    import base64

    credentials = f"{client_id}:{client_secret}".encode()
    b64 = base64.b64encode(credentials).decode("ascii")
    return f"Basic {b64}"


@router.get("/auth/notion/connector/add")
async def connect_notion(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Notion OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.NOTION_CLIENT_ID:
            raise HTTPException(
                status_code=500, detail="Notion OAuth not configured."
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
            "client_id": config.NOTION_CLIENT_ID,
            "response_type": "code",
            "owner": "user",  # Allows both admins and members to authorize
            "redirect_uri": config.NOTION_REDIRECT_URI,
            "state": state_encoded,
        }

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(
            f"Generated Notion OAuth URL for user {user.id}, space {space_id}"
        )
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate Notion OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Notion OAuth: {e!s}"
        ) from e


@router.get("/auth/notion/connector/callback")
async def notion_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Notion OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from Notion (if user granted access)
        error: Error code from Notion (if user denied access or error occurred)
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Notion OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=notion_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=notion_oauth_denied"
                )
        
        # Validate required parameters for successful flow
        if not code:
            raise HTTPException(
                status_code=400, detail="Missing authorization code"
            )
        if not state:
            raise HTTPException(
                status_code=400, detail="Missing state parameter"
            )

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
        # Note: Notion doesn't send redirect_uri in callback, but we validate
        # that we're using the configured one in token exchange
        if not config.NOTION_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="NOTION_REDIRECT_URI not configured"
            )

        # Exchange authorization code for access token
        auth_header = make_basic_auth_header(
            config.NOTION_CLIENT_ID, config.NOTION_CLIENT_SECRET
        )

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.NOTION_REDIRECT_URI,  # Use stored value, not from request
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                json=token_data,
                headers={
                    "Content-Type": "application/json",
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
        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Notion"
            )

        # Notion returns access_token and workspace information
        # Store the encrypted access token and workspace info in connector config
        connector_config = {
            "access_token": token_encryption.encrypt_token(access_token),
            "workspace_id": token_json.get("workspace_id"),
            "workspace_name": token_json.get("workspace_name"),
            "workspace_icon": token_json.get("workspace_icon"),
            "bot_id": token_json.get("bot_id"),
            # Mark that token is encrypted for backward compatibility
            "_token_encrypted": True,
        }

        # Check if connector already exists for this search space and user
        existing_connector_result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.NOTION_CONNECTOR,
            )
        )
        existing_connector = existing_connector_result.scalars().first()

        if existing_connector:
            # Update existing connector
            existing_connector.config = connector_config
            existing_connector.name = "Notion Connector"
            existing_connector.is_indexable = True
            logger.info(
                f"Updated existing Notion connector for user {user_id} in space {space_id}"
            )
        else:
            # Create new connector
            new_connector = SearchSourceConnector(
                name="Notion Connector",
                connector_type=SearchSourceConnectorType.NOTION_CONNECTOR,
                is_indexable=True,
                config=connector_config,
                search_space_id=space_id,
                user_id=user_id,
            )
            session.add(new_connector)
            logger.info(
                f"Created new Notion connector for user {user_id} in space {space_id}"
            )

        try:
            await session.commit()
            logger.info(f"Successfully saved Notion connector for user {user_id}")

            # Redirect to the frontend with success params
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=notion-connector"
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
        logger.error(f"Failed to complete Notion OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Notion OAuth: {e!s}"
        ) from e

