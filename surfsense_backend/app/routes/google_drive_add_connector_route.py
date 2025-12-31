"""
Google Drive Connector OAuth Routes.

Handles OAuth 2.0 authentication flow for Google Drive connector.
Folder selection happens at index time on the manage connector page.

Endpoints:
- GET /auth/google/drive/connector/add - Initiate OAuth
- GET /auth/google/drive/connector/callback - Handle OAuth callback
- GET /connectors/{connector_id}/google-drive/folders - List user's folders (for index-time selection)
"""

import base64
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
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.users import current_active_user

# Relax token scope validation for Google OAuth
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

logger = logging.getLogger(__name__)
router = APIRouter()

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

        flow = get_google_flow()

        # Encode space_id and user_id in state parameter
        state_payload = json.dumps(
            {
                "space_id": space_id,
                "user_id": str(user.id),
            }
        )
        state_encoded = base64.urlsafe_b64encode(state_payload.encode()).decode()

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
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Google Drive OAuth callback.

    Query params:
        code: Authorization code from Google
        state: Encoded state with space_id and user_id

    Returns:
        Redirect to frontend success page
    """
    try:
        # Decode and parse state
        decoded_state = base64.urlsafe_b64decode(state.encode()).decode()
        data = json.loads(decoded_state)

        user_id = UUID(data["user_id"])
        space_id = data["space_id"]

        logger.info(
            f"Processing Google Drive callback for user {user_id}, space {space_id}"
        )

        # Exchange authorization code for tokens
        flow = get_google_flow()
        flow.fetch_token(code=code)

        creds = flow.credentials
        creds_dict = json.loads(creds.to_json())

        # Check if connector already exists for this space/user
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
            )
        )
        existing_connector = result.scalars().first()

        if existing_connector:
            raise HTTPException(
                status_code=409,
                detail="A GOOGLE_DRIVE_CONNECTOR already exists in this search space. Each search space can have only one connector of each type per user.",
            )

        # Create new connector (NO folder selection here - happens at index time)
        db_connector = SearchSourceConnector(
            name="Google Drive Connector",
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
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=google-drive-connector"
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
            detail="A connector with this configuration already exists.",
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
            f"✅ Listed {len(items)} total items ({folder_count} folders, {file_count} files) for connector {connector_id}"
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
