import os

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import base64
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
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

logger = logging.getLogger(__name__)

router = APIRouter()


def get_google_flow():
    """Create and return a Google OAuth flow for Gmail API."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [config.GOOGLE_GMAIL_REDIRECT_URI],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid",
        ],
    )
    flow.redirect_uri = config.GOOGLE_GMAIL_REDIRECT_URI
    return flow


@router.get("/auth/google/gmail/connector/add")
async def connect_gmail(space_id: int, user: User = Depends(current_active_user)):
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        flow = get_google_flow()

        # Encode space_id and user_id in state
        state_payload = json.dumps(
            {
                "space_id": space_id,
                "user_id": str(user.id),
            }
        )
        state_encoded = base64.urlsafe_b64encode(state_payload.encode()).decode()

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


@router.get("/auth/google/gmail/connector/callback")
async def gmail_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        # Decode and parse the state
        decoded_state = base64.urlsafe_b64decode(state.encode()).decode()
        data = json.loads(decoded_state)

        user_id = UUID(data["user_id"])
        space_id = data["space_id"]

        flow = get_google_flow()
        flow.fetch_token(code=code)

        creds = flow.credentials
        creds_dict = json.loads(creds.to_json())

        try:
            # Check if a connector with the same type already exists for this search space and user
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id == space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
                )
            )
            existing_connector = result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail="A GOOGLE_GMAIL_CONNECTOR connector already exists in this search space. Each search space can have only one connector of each type per user.",
                )
            db_connector = SearchSourceConnector(
                name="Google Gmail Connector",
                connector_type=SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
                config=creds_dict,
                search_space_id=space_id,
                user_id=user_id,
                is_indexable=True,
            )
            session.add(db_connector)
            await session.commit()
            await session.refresh(db_connector)

            logger.info(
                f"Successfully created Gmail connector for user {user_id} with ID {db_connector.id}"
            )

            # Redirect to the frontend success page
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/add/google-gmail-connector?success=true"
            )

        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Database integrity error: {e!s}")
            raise HTTPException(
                status_code=409,
                detail="A connector with this configuration already exists.",
            ) from e
        except ValidationError as e:
            await session.rollback()
            logger.error(f"Validation error: {e!s}")
            raise HTTPException(
                status_code=400, detail=f"Invalid connector configuration: {e!s}"
            ) from e

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Gmail callback: {e!s}", exc_info=True)
