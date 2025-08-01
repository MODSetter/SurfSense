# app/routes/google_calendar.py

import base64
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import GoogleCalendarAccount, User, get_async_session
from app.users import current_active_user

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


@router.get("/auth/google/calendar/connector/init/")
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


@router.get("/auth/google/calendar/connector/callback/")
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
        token = creds.token
        refresh_token = creds.refresh_token

        existing = await session.scalar(
            select(GoogleCalendarAccount).where(
                GoogleCalendarAccount.user_id == user_id
            )
        )
        if existing:
            existing.access_token = token
            existing.refresh_token = refresh_token or existing.refresh_token
        else:
            session.add(
                GoogleCalendarAccount(
                    user_id=user_id,
                    access_token=token,
                    refresh_token=refresh_token,
                )
            )

        await session.commit()

        return RedirectResponse(
            f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/add/google-calendar-connector?success=true"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Google OAuth: {e!s}"
        ) from e
