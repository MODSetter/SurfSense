"""
Google Drive Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Google Drive connector.
Folder selection happens at index time on the manage connector page.

Endpoints:
- GET /auth/google/drive/connector/add - Initiate OAuth
- GET /auth/google/drive/connector/callback - Handle OAuth callback
- GET /connectors/{connector_id}/google-drive/folders - List user's folders (for index-time selection)
"""

import json
import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.connectors.google_drive import (
    GoogleDriveClient,
    get_start_page_token,
    list_folder_contents,
)
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

# Relax token scope validation for Google OAuth
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

logger = logging.getLogger(__name__)
router = APIRouter()

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


# Google Drive OAuth scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",  # Read-only access to Drive
    "https://www.googleapis.com/auth/userinfo.email",  # User email
    "https://www.googleapis.com/auth/userinfo.profile",  # User profile
    "openid",
]


def get_google_flow():
    """Create and return a Google OAuth flow for Drive API."""
    try:
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [config.GOOGLE_DRIVE_REDIRECT_URI],
                }
            },
            scopes=SCOPES,
            redirect_uri=config.GOOGLE_DRIVE_REDIRECT_URI,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create Google OAuth flow: {e!s}"
        ) from e


@router.get("/auth/google/drive/connector/add")
async def connect_drive(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Google Drive OAuth flow.

    Query params:
        space_id: Search space ID to add connector to

    Returns:
        JSON with auth_url to redirect user to Google authorization
    """
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

        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            access_type="offline",  # Get refresh token
            prompt="consent",  # Force consent screen to get refresh token
            include_granted_scopes="true",
            state=state_encoded,
        )

        logger.info(
            f"Initiating Google Drive OAuth for user {user.id}, space {space_id}"
        )
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate Google Drive OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Google OAuth: {e!s}"
        ) from e


@router.get("/auth/google/drive/connector/callback")
async def drive_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Google Drive OAuth callback.

    Query params:
        code: Authorization code from Google
        error: OAuth error (if user denied access)
        state: Encoded state with space_id and user_id

    Returns:
        Redirect to frontend success page
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Google Drive OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=google_drive_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=google_drive_oauth_denied"
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

        logger.info(
            f"Processing Google Drive callback for user {user_id}, space {space_id}"
        )

        # Validate redirect URI (security: ensure it matches configured value)
        if not config.GOOGLE_DRIVE_REDIRECT_URI:
            raise HTTPException(
                status_code=500, detail="GOOGLE_DRIVE_REDIRECT_URI not configured"
            )

        # Exchange authorization code for tokens
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
            SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
            space_id,
            user_id,
            user_email,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Google Drive connector detected for user {user_id} with email {user_email}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=google-drive-connector"
            )

        # Generate a unique, user-friendly connector name
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
            space_id,
            user_id,
            user_email,
        )

        db_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
            config={
                **creds_dict,
                "start_page_token": None,  # Will be set on first index
            },
            search_space_id=space_id,
            user_id=user_id,
            is_indexable=True,
        )

        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        # Get initial start page token for delta sync
        try:
            drive_client = GoogleDriveClient(session, db_connector.id)
            start_token, token_error = await get_start_page_token(drive_client)

            if start_token and not token_error:
                db_connector.config["start_page_token"] = start_token
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(db_connector, "config")
                await session.commit()
                logger.info(
                    f"Set initial start page token for connector {db_connector.id}"
                )
        except Exception as e:
            logger.warning(f"Failed to get initial start page token: {e!s}")

        logger.info(
            f"Successfully created Google Drive connector {db_connector.id} for user {user_id}"
        )

        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=google-drive-connector&connectorId={db_connector.id}"
        )

    except HTTPException:
        await session.rollback()
        raise
    except ValidationError as e:
        await session.rollback()
        logger.error(f"Validation error: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=400, detail=f"Invalid connector configuration: {e!s}"
        ) from e
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=409,
            detail=f"Database integrity error: {e!s}",
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error in Drive callback: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Google OAuth: {e!s}"
        ) from e


@router.get("/connectors/{connector_id}/google-drive/folders")
async def list_google_drive_folders(
    connector_id: int,
    parent_id: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List folders AND files in user's Google Drive with hierarchical support.

    This is called at index time from the manage connector page to display
    the complete file system (folders and files). Only folders are selectable.

    Args:
        connector_id: ID of the Google Drive connector
        parent_id: Optional parent folder ID to list contents (None for root)

    Returns:
        JSON with list of items: {
            "items": [
                {"id": str, "name": str, "mimeType": str, "isFolder": bool, ...},
                ...
            ]
        }
    """
    try:
        # Get connector and verify ownership
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="Google Drive connector not found or access denied",
            )

        # Initialize Drive client (credentials will be loaded on first API call)
        drive_client = GoogleDriveClient(session, connector_id)

        # List both folders and files (sorted: folders first)
        items, error = await list_folder_contents(drive_client, parent_id=parent_id)

        if error:
            raise HTTPException(
                status_code=500, detail=f"Failed to list folder contents: {error}"
            )

        # Count folders and files for better logging
        folder_count = sum(1 for item in items if item.get("isFolder", False))
        file_count = len(items) - folder_count

        logger.info(
            f"Listed {len(items)} total items ({folder_count} folders, {file_count} files) for connector {connector_id}"
            + (f" in folder {parent_id}" if parent_id else " in ROOT")
        )

        # Log first few items for debugging
        if items:
            logger.info(f"First 3 items: {[item.get('name') for item in items[:3]]}")

        return {"items": items}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Drive contents: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list Drive contents: {e!s}"
        ) from e
