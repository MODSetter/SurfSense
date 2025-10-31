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

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REDIRECT_URI = config.GOOGLE_CALENDAR_REDIRECT_URI


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


@router.get("/auth/google/calendar/connector/callback")
async def calendar_callback(
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
                    == SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                )
            )
            existing_connector = result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail="A GOOGLE_CALENDAR_CONNECTOR connector already exists in this search space. Each search space can have only one connector of each type per user.",
                )
            db_connector = SearchSourceConnector(
                name="Google Calendar Connector",
                connector_type=SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                config=creds_dict,
                search_space_id=space_id,
                user_id=user_id,
                is_indexable=True,
            )
            session.add(db_connector)
            await session.commit()
            await session.refresh(db_connector)
            return RedirectResponse(
                f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/add/google-calendar-connector?success=true"
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
