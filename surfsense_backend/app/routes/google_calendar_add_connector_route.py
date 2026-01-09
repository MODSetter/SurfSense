import os

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.google_gmail_connector import fetch_google_user_email
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter()

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REDIRECT_URI = config.GOOGLE_CALENDAR_REDIRECT_URI

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


def get_google_flow():
    try:
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create Google flow: {e!s}"
        ) from e


@router.get("/auth/google/calendar/connector/add")
async def connect_calendar(space_id: int, user: User = Depends(current_active_user)):
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.SECRET_KEY:
            raise HTTPException(
                status_code=500, detail="SECRET_KEY not configured for OAuth security."
            )

        flow = get_google_flow()

        # Generate secure state parameter with HMAC signature
        state_manager = get_state_manager()
        state_encoded = state_manager.generate_secure_state(space_id, user.id)

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
            state=state_encoded,
        )
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Google OAuth: {e!s}"
        ) from e


@router.get("/auth/google/calendar/connector/callback")
async def calendar_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Google Calendar OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=google_calendar_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=google_calendar_oauth_denied"
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
        if not config.GOOGLE_CALENDAR_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="GOOGLE_CALENDAR_REDIRECT_URI not configured"
            )

        flow = get_google_flow()
        flow.fetch_token(code=code)

        creds = flow.credentials
        creds_dict = json.loads(creds.to_json())

        # Fetch user email
        user_email = fetch_google_user_email(creds)

        # Encrypt sensitive credentials before storing
        token_encryption = get_token_encryption()

        # Encrypt sensitive fields: token, refresh_token, client_secret
        if creds_dict.get("token"):
            creds_dict["token"] = token_encryption.encrypt_token(creds_dict["token"])
        if creds_dict.get("refresh_token"):
            creds_dict["refresh_token"] = token_encryption.encrypt_token(
                creds_dict["refresh_token"]
            )
        if creds_dict.get("client_secret"):
            creds_dict["client_secret"] = token_encryption.encrypt_token(
                creds_dict["client_secret"]
            )

        # Mark that credentials are encrypted for backward compatibility
        creds_dict["_token_encrypted"] = True

        # Check for duplicate connector (same account already connected)
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
            space_id,
            user_id,
            user_email,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Google Calendar connector detected for user {user_id} with email {user_email}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=google-calendar-connector"
            )

        try:
            # Generate a unique, user-friendly connector name
            connector_name = await generate_unique_connector_name(
                session,
                SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                space_id,
                user_id,
                user_email,
            )
            db_connector = SearchSourceConnector(
                name=connector_name,
                connector_type=SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                config=creds_dict,
                search_space_id=space_id,
                user_id=user_id,
                is_indexable=True,
            )
            session.add(db_connector)
            await session.commit()
            await session.refresh(db_connector)
            # Redirect to the frontend with success params for indexing config
            # Using query params to auto-open the popup with config view on new-chat page
            return RedirectResponse(
                f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=google-calendar-connector&connectorId={db_connector.id}"
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
        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to create search source connector: {e!s}")
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create search source connector: {e!s}",
            ) from e

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Google OAuth: {e!s}"
        ) from e
