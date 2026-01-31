import base64
import hashlib
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

from app.config import config
from app.connectors.airtable_connector import fetch_airtable_user_email
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

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

        if not config.SECRET_KEY:
            raise HTTPException(
                status_code=500, detail="SECRET_KEY not configured for OAuth security."
            )

        # Generate PKCE parameters
        code_verifier, code_challenge = generate_pkce_pair()

        # Generate secure state parameter with HMAC signature (including code_verifier for PKCE)
        state_manager = get_state_manager()
        state_encoded = state_manager.generate_secure_state(
            space_id, user.id, code_verifier=code_verifier
        )

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
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Handle Airtable OAuth callback.

    Args:
        request: FastAPI request object
        code: Authorization code from Airtable (if user granted access)
        error: Error code from Airtable (if user denied access or error occurred)
        state: State parameter containing user/space info
        session: Database session

    Returns:
        Redirect response to frontend
    """
    try:
        # Handle OAuth errors (e.g., user denied access)
        if error:
            logger.warning(f"Airtable OAuth error: {error}")
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
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=airtable_oauth_denied"
                )
            else:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=airtable_oauth_denied"
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
        code_verifier = data.get("code_verifier")

        if not code_verifier:
            raise HTTPException(
                status_code=400, detail="Missing code_verifier in state parameter"
            )
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

        # Encrypt sensitive tokens before storing
        token_encryption = get_token_encryption()
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Airtable"
            )

        user_email = await fetch_airtable_user_email(access_token)

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Create credentials object with encrypted tokens
        credentials = AirtableAuthCredentialsBase(
            access_token=token_encryption.encrypt_token(access_token),
            refresh_token=token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            token_type=token_json.get("token_type", "Bearer"),
            expires_in=token_json.get("expires_in"),
            expires_at=expires_at,
            scope=token_json.get("scope"),
        )

        # Mark that tokens are encrypted for backward compatibility
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True

        # Check for duplicate connector (same account already connected)
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.AIRTABLE_CONNECTOR,
            space_id,
            user_id,
            user_email,
        )
        if is_duplicate:
            logger.warning(
                f"Duplicate Airtable connector detected for user {user_id} with email {user_email}"
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&error=duplicate_account&connector=airtable-connector"
            )

        # Generate a unique, user-friendly connector name
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.AIRTABLE_CONNECTOR,
            space_id,
            user_id,
            user_email,
        )
        # Create new connector
        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.AIRTABLE_CONNECTOR,
            is_indexable=True,
            config=credentials_dict,
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

            # Redirect to the frontend with success params for indexing config
            # Using query params to auto-open the popup with config view on new-chat page
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/new-chat?modal=connectors&tab=all&success=true&connector=airtable-connector&connectorId={new_connector.id}"
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
        logger.error(f"Failed to complete Airtable OAuth: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to complete Airtable OAuth: {e!s}"
        ) from e


async def refresh_airtable_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
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
            config.AIRTABLE_CLIENT_ID, config.AIRTABLE_CLIENT_SECRET
        )

        # Prepare token refresh data
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
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
                    detail="Airtable authentication failed. Please re-authenticate.",
                )
            raise HTTPException(
                status_code=400, detail=f"Token refresh failed: {error_detail}"
            )

        token_json = token_response.json()

        # Calculate expiration time (UTC, tz-aware)
        expires_at = None
        if token_json.get("expires_in"):
            now_utc = datetime.now(UTC)
            expires_at = now_utc + timedelta(seconds=int(token_json["expires_in"]))

        # Encrypt new tokens before storing
        access_token = token_json.get("access_token")
        new_refresh_token = token_json.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Airtable refresh"
            )

        # Update credentials object with encrypted tokens
        credentials.access_token = token_encryption.encrypt_token(access_token)
        if new_refresh_token:
            credentials.refresh_token = token_encryption.encrypt_token(
                new_refresh_token
            )
        credentials.expires_in = token_json.get("expires_in")
        credentials.expires_at = expires_at
        credentials.scope = token_json.get("scope")

        # Update connector config with encrypted tokens
        credentials_dict = credentials.to_dict()
        credentials_dict["_token_encrypted"] = True
        connector.config = credentials_dict
        await session.commit()
        await session.refresh(connector)

        logger.info(
            f"Successfully refreshed Airtable token for connector {connector.id}"
        )

        return connector
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh Airtable token: {e!s}"
        ) from e
