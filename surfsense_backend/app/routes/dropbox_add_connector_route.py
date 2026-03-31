"""
Dropbox Connector OAuth Routes.

Endpoints:
- GET /auth/dropbox/connector/add     - Initiate OAuth
- GET /auth/dropbox/connector/callback - Handle OAuth callback
- GET /auth/dropbox/connector/reauth   - Re-authenticate existing connector
- GET /connectors/{connector_id}/dropbox/folders - List folder contents
"""

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.config import config
from app.connectors.dropbox import DropboxClient, list_folder_contents
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    extract_identifier_from_credentials,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)
router = APIRouter()

AUTHORIZATION_URL = "https://www.dropbox.com/oauth2/authorize"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"

_state_manager = None
_token_encryption = None


def get_state_manager() -> OAuthStateManager:
    global _state_manager
    if _state_manager is None:
        if not config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set for OAuth security")
        _state_manager = OAuthStateManager(config.SECRET_KEY)
    return _state_manager


def get_token_encryption() -> TokenEncryption:
    global _token_encryption
    if _token_encryption is None:
        if not config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set for token encryption")
        _token_encryption = TokenEncryption(config.SECRET_KEY)
    return _token_encryption


@router.get("/auth/dropbox/connector/add")
async def connect_dropbox(space_id: int, user: User = Depends(current_active_user)):
    """Initiate Dropbox OAuth flow."""
    try:
        if not space_id:
            raise HTTPException(status_code=400, detail="space_id is required")
        if not config.DROPBOX_APP_KEY:
            raise HTTPException(
                status_code=500, detail="Dropbox OAuth not configured."
            )
        if not config.SECRET_KEY:
            raise HTTPException(
                status_code=500, detail="SECRET_KEY not configured for OAuth security."
            )

        state_manager = get_state_manager()
        state_encoded = state_manager.generate_secure_state(space_id, user.id)

        auth_params = {
            "client_id": config.DROPBOX_APP_KEY,
            "response_type": "code",
            "redirect_uri": config.DROPBOX_REDIRECT_URI,
            "state": state_encoded,
            "token_access_type": "offline",
        }
        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(
            "Generated Dropbox OAuth URL for user %s, space %s", user.id, space_id
        )
        return {"auth_url": auth_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to initiate Dropbox OAuth: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Dropbox OAuth: {e!s}"
        ) from e


@router.get("/auth/dropbox/connector/reauth")
async def reauth_dropbox(
    space_id: int,
    connector_id: int,
    return_url: str | None = None,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Re-authenticate an existing Dropbox connector."""
    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DROPBOX_CONNECTOR,
            )
        )
        connector = result.scalars().first()
        if not connector:
            raise HTTPException(
                status_code=404, detail="Dropbox connector not found or access denied"
            )

        if not config.SECRET_KEY:
            raise HTTPException(
                status_code=500, detail="SECRET_KEY not configured for OAuth security."
            )

        state_manager = get_state_manager()
        extra: dict = {"connector_id": connector_id}
        if return_url and return_url.startswith("/"):
            extra["return_url"] = return_url
        state_encoded = state_manager.generate_secure_state(space_id, user.id, **extra)

        auth_params = {
            "client_id": config.DROPBOX_APP_KEY,
            "response_type": "code",
            "redirect_uri": config.DROPBOX_REDIRECT_URI,
            "state": state_encoded,
            "token_access_type": "offline",
            "force_reapprove": "true",
        }
        auth_url = f"{AUTHORIZATION_URL}?{urlencode(auth_params)}"

        logger.info(
            "Initiating Dropbox re-auth for user %s, connector %s",
            user.id,
            connector_id,
        )
        return {"auth_url": auth_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to initiate Dropbox re-auth: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Dropbox re-auth: {e!s}"
        ) from e


@router.get("/auth/dropbox/connector/callback")
async def dropbox_callback(
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """Handle Dropbox OAuth callback."""
    try:
        if error:
            error_msg = error_description or error
            logger.warning("Dropbox OAuth error: %s", error_msg)
            space_id = None
            if state:
                try:
                    data = get_state_manager().validate_state(state)
                    space_id = data.get("space_id")
                except Exception:
                    pass
            if space_id:
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?error=dropbox_oauth_denied"
                )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=dropbox_oauth_denied"
            )

        if not code or not state:
            raise HTTPException(
                status_code=400, detail="Missing required OAuth parameters"
            )

        state_manager = get_state_manager()
        try:
            data = state_manager.validate_state(state)
            space_id = data["space_id"]
            user_id = UUID(data["user_id"])
        except (HTTPException, ValueError, KeyError) as e:
            logger.error("Invalid OAuth state: %s", str(e))
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=invalid_state"
            )

        reauth_connector_id = data.get("connector_id")
        reauth_return_url = data.get("return_url")

        token_data = {
            "client_id": config.DROPBOX_APP_KEY,
            "client_secret": config.DROPBOX_APP_SECRET,
            "code": code,
            "redirect_uri": config.DROPBOX_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
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
        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token")

        if not access_token:
            raise HTTPException(
                status_code=400, detail="No access token received from Dropbox"
            )

        token_encryption = get_token_encryption()

        expires_at = None
        if token_json.get("expires_in"):
            expires_at = datetime.now(UTC) + timedelta(
                seconds=int(token_json["expires_in"])
            )

        user_info: dict = {}
        try:
            async with httpx.AsyncClient() as client:
                user_response = await client.post(
                    "https://api.dropboxapi.com/2/users/get_current_account",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    content=b"null",
                    timeout=30.0,
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    user_info = {
                        "user_email": user_data.get("email"),
                        "user_name": user_data.get("name", {}).get("display_name"),
                        "account_id": user_data.get("account_id"),
                    }
        except Exception as e:
            logger.warning("Failed to fetch user info from Dropbox: %s", str(e))

        connector_config = {
            "access_token": token_encryption.encrypt_token(access_token),
            "refresh_token": token_encryption.encrypt_token(refresh_token)
            if refresh_token
            else None,
            "token_type": token_json.get("token_type", "bearer"),
            "expires_in": token_json.get("expires_in"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "user_email": user_info.get("user_email"),
            "user_name": user_info.get("user_name"),
            "account_id": user_info.get("account_id"),
            "_token_encrypted": True,
        }

        if reauth_connector_id:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == reauth_connector_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.search_space_id == space_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.DROPBOX_CONNECTOR,
                )
            )
            db_connector = result.scalars().first()
            if not db_connector:
                raise HTTPException(
                    status_code=404,
                    detail="Connector not found or access denied during re-auth",
                )

            existing_cursor = db_connector.config.get("cursor")
            db_connector.config = {
                **connector_config,
                "cursor": existing_cursor,
                "auth_expired": False,
            }
            flag_modified(db_connector, "config")
            await session.commit()
            await session.refresh(db_connector)

            logger.info(
                "Re-authenticated Dropbox connector %s for user %s",
                db_connector.id,
                user_id,
            )
            if reauth_return_url and reauth_return_url.startswith("/"):
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}{reauth_return_url}"
                )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?success=true&connector=DROPBOX_CONNECTOR&connectorId={db_connector.id}"
            )

        connector_identifier = extract_identifier_from_credentials(
            SearchSourceConnectorType.DROPBOX_CONNECTOR, connector_config
        )
        is_duplicate = await check_duplicate_connector(
            session,
            SearchSourceConnectorType.DROPBOX_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )
        if is_duplicate:
            logger.warning(
                "Duplicate Dropbox connector for user %s, space %s", user_id, space_id
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?error=duplicate_account&connector=DROPBOX_CONNECTOR"
            )

        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.DROPBOX_CONNECTOR,
            space_id,
            user_id,
            connector_identifier,
        )

        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.DROPBOX_CONNECTOR,
            is_indexable=True,
            config=connector_config,
            search_space_id=space_id,
            user_id=user_id,
        )

        try:
            session.add(new_connector)
            await session.commit()
            await session.refresh(new_connector)
            logger.info(
                "Successfully created Dropbox connector %s for user %s",
                new_connector.id,
                user_id,
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?success=true&connector=DROPBOX_CONNECTOR&connectorId={new_connector.id}"
            )
        except IntegrityError as e:
            await session.rollback()
            logger.error(
                "Database integrity error creating Dropbox connector: %s", str(e)
            )
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=connector_creation_failed"
            )

    except HTTPException:
        raise
    except (IntegrityError, ValueError) as e:
        logger.error("Dropbox OAuth callback error: %s", str(e), exc_info=True)
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=dropbox_auth_error"
        )


@router.get("/connectors/{connector_id}/dropbox/folders")
async def list_dropbox_folders(
    connector_id: int,
    parent_path: str = "",
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """List folders and files in user's Dropbox."""
    connector = None
    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DROPBOX_CONNECTOR,
            )
        )
        connector = result.scalars().first()
        if not connector:
            raise HTTPException(
                status_code=404, detail="Dropbox connector not found or access denied"
            )

        dropbox_client = DropboxClient(session, connector_id)
        items, error = await list_folder_contents(dropbox_client, path=parent_path)

        if error:
            error_lower = error.lower()
            if (
                "401" in error
                or "authentication expired" in error_lower
                or "expired_access_token" in error_lower
            ):
                try:
                    if connector and not connector.config.get("auth_expired"):
                        connector.config = {**connector.config, "auth_expired": True}
                        flag_modified(connector, "config")
                        await session.commit()
                except Exception:
                    logger.warning(
                        "Failed to persist auth_expired for connector %s",
                        connector_id,
                        exc_info=True,
                    )
                raise HTTPException(
                    status_code=400,
                    detail="Dropbox authentication expired. Please re-authenticate.",
                )
            raise HTTPException(
                status_code=500, detail=f"Failed to list folder contents: {error}"
            )

        return {"items": items}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing Dropbox contents: %s", str(e), exc_info=True)
        error_lower = str(e).lower()
        if "401" in str(e) or "authentication expired" in error_lower:
            try:
                if connector and not connector.config.get("auth_expired"):
                    connector.config = {**connector.config, "auth_expired": True}
                    flag_modified(connector, "config")
                    await session.commit()
            except Exception:
                pass
            raise HTTPException(
                status_code=400,
                detail="Dropbox authentication expired. Please re-authenticate.",
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Failed to list Dropbox contents: {e!s}"
        ) from e


async def refresh_dropbox_token(
    session: AsyncSession, connector: SearchSourceConnector
) -> SearchSourceConnector:
    """Refresh Dropbox OAuth tokens."""
    logger.info("Refreshing Dropbox OAuth tokens for connector %s", connector.id)

    token_encryption = get_token_encryption()
    is_encrypted = connector.config.get("_token_encrypted", False)
    refresh_token = connector.config.get("refresh_token")

    if is_encrypted and refresh_token:
        try:
            refresh_token = token_encryption.decrypt_token(refresh_token)
        except Exception as e:
            logger.error("Failed to decrypt refresh token: %s", str(e))
            raise HTTPException(
                status_code=500, detail="Failed to decrypt stored refresh token"
            ) from e

    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail=f"No refresh token available for connector {connector.id}",
        )

    refresh_data = {
        "client_id": config.DROPBOX_APP_KEY,
        "client_secret": config.DROPBOX_APP_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            TOKEN_URL,
            data=refresh_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
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
        error_lower = (error_detail + error_code).lower()
        if (
            "invalid_grant" in error_lower
            or "expired" in error_lower
            or "revoked" in error_lower
        ):
            raise HTTPException(
                status_code=401,
                detail="Dropbox authentication failed. Please re-authenticate.",
            )
        raise HTTPException(
            status_code=400, detail=f"Token refresh failed: {error_detail}"
        )

    token_json = token_response.json()
    access_token = token_json.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=400, detail="No access token received from Dropbox refresh"
        )

    expires_at = None
    expires_in = token_json.get("expires_in")
    if expires_in:
        expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

    cfg = dict(connector.config)
    cfg["access_token"] = token_encryption.encrypt_token(access_token)
    cfg["expires_in"] = expires_in
    cfg["expires_at"] = expires_at.isoformat() if expires_at else None
    cfg["_token_encrypted"] = True
    cfg.pop("auth_expired", None)

    connector.config = cfg
    flag_modified(connector, "config")
    await session.commit()
    await session.refresh(connector)

    logger.info("Successfully refreshed Dropbox tokens for connector %s", connector.id)
    return connector
