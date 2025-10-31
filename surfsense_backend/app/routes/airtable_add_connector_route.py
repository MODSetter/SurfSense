import base64
import hashlib
import json
import logging
import secrets
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
from app.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Airtable OAuth endpoints
AUTHORIZATION_URL = "https://airtable.com/oauth2/v1/authorize"
TOKEN_URL = "https://airtable.com/oauth2/v1/token"

# OAuth scopes for Airtable
SCOPES = [
    "data.records:read",
    "data.recordComments:read",
    "schema.bases:read",
    "user.email:read",
]


def make_basic_auth_header(client_id: str, client_secret: str) -> str:
    credentials = f"{client_id}:{client_secret}".encode()
    b64 = base64.b64encode(credentials).decode("ascii")
    return f"Basic {b64}"


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate PKCE code verifier and code challenge.

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate code verifier (43-128 characters)
    code_verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    )

    # Generate code challenge (SHA256 hash of verifier, base64url encoded)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("utf-8")).digest())
        .decode("utf-8")
        .rstrip("=")
    )

    return code_verifier, code_challenge


@router.get("/auth/airtable/connector/add")
async def connect_airtable(space_id: int, user: User = Depends(current_active_user)):
    """
    Initiate Airtable OAuth flow.

    Args:
        space_id: The search space ID
        user: Current authenticated user

    Returns:
        Authorization URL for redirect
    """
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")

        if not config.AIRTABLE_CLIENT_ID:
            raise HTTPException(
                status_code=500, detail="Airtable OAuth not configured."
            )

        # Generate PKCE parameters
        code_verifier, code_challenge = generate_pkce_pair()

        # Generate state parameter
        state_payload = json.dumps(
            {
                "space_id": space_id,
                "user_id": str(user.id),
                "code_verifier": code_verifier,
            }
        )
        state_encoded = base64.urlsafe_b64encode(state_payload.encode()).decode()

        # Build authorization URL
        auth_params = {
            "client_id": config.AIRTABLE_CLIENT_ID,
            "redirect_uri": config.AIRTABLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "state": state_encoded,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        # Construct URL manually to ensure proper encoding
        from urllib.parse import urlencode

        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(
            f"Generated Airtable OAuth URL for user {user.id}, space {space_id}"
        )
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error(f"Failed to initiate Airtable OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Airtable OAuth: {e!s}"
        ) from e


@router.get("/auth/airtable/connector/callback")
async def airtable_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Airtable OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from Airtable
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Decode and parse the state
        try:
            decoded_state = base64.urlsafe_b64decode(state.encode()).decode()
            data = json.loads(decoded_state)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid state parameter: {e!s}"
            ) from e

        user_id = UUID(data["user_id"])
        space_id = data["space_id"]
        code_verifier = data["code_verifier"]
        auth_header = make_basic_auth_header(
            config.AIRTABLE_CLIENT_ID, config.AIRTABLE_CLIENT_SECRET
        )

        # Exchange authorization code for access token
        token_data = {
            "client_id": config.AIRTABLE_CLIENT_ID,
            "client_secret": config.AIRTABLE_CLIENT_SECRET,
            "redirect_uri": config.AIRTABLE_REDIRECT_URI,
            "code": code,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
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

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Create credentials object
        credentials = AirtableAuthCredentialsBase(
            access_token=token_json["access_token"],
            refresh_token=token_json.get("refresh_token"),
            token_type=token_json.get("token_type", "Bearer"),
            expires_in=token_json.get("expires_in"),
            expires_at=expires_at,
            scope=token_json.get("scope"),
        )

        # Check if connector already exists for this search space and user
        existing_connector_result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.AIRTABLE_CONNECTOR,
            )
        )
        existing_connector = existing_connector_result.scalars().first()

        if existing_connector:
            # Update existing connector
            existing_connector.config = credentials.to_dict()
            existing_connector.name = "Airtable Connector"
            existing_connector.is_indexable = True
            logger.info(
                f"Updated existing Airtable connector for user {user_id} in space {space_id}"
            )
        else:
            # Create new connector
            new_connector = SearchSourceConnector(
                name="Airtable Connector",
                connector_type=SearchSourceConnectorType.AIRTABLE_CONNECTOR,
                is_indexable=True,
                config=credentials.to_dict(),
                search_space_id=space_id,
                user_id=user_id,
            )
            session.add(new_connector)
            logger.info(
                f"Created new Airtable connector for user {user_id} in space {space_id}"
            )

        try:
            await session.commit()
            logger.info(f"Successfully saved Airtable connector for user {user_id}")

            # Redirect to the frontend success page
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/add/airtable-connector?success=true"
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
        logger.error(f"Failed to complete Airtable OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Airtable OAuth: {e!s}"
        ) from e


async def refresh_airtable_token(
    session: AsyncSession, connector: SearchSourceConnector
):
    """
    Refresh the Airtable access token for a connector.

    Args:
        session: Database session
        connector: Airtable connector to refresh

    Returns:
        Updated connector object
    """
    try:
        logger.info(f"Refreshing Airtable token for connector {connector.id}")

        credentials = AirtableAuthCredentialsBase.from_dict(connector.config)
        auth_header = make_basic_auth_header(
            config.AIRTABLE_CLIENT_ID, config.AIRTABLE_CLIENT_SECRET
        )

        # Prepare token refresh data
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": credentials.refresh_token,
            "client_id": config.AIRTABLE_CLIENT_ID,
            "client_secret": config.AIRTABLE_CLIENT_SECRET,
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
            raise HTTPException(
                status_code=400, detail="Token refresh failed: {token_response.text}"
            )

        token_json = token_response.json()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Update credentials object
        credentials.access_token = token_json["access_token"]
        credentials.expires_in = token_json.get("expires_in")
        credentials.expires_at = expires_at
        credentials.scope = token_json.get("scope")

        # Update connector config
        connector.config = credentials.to_dict()
        await session.commit()
        await session.refresh(connector)

        logger.info(
            f"Successfully refreshed Airtable token for connector {connector.id}"
        )

        return connector
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Airtable token: {e!s}"
        ) from e
