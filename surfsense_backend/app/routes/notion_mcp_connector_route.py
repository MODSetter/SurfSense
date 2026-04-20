"""Notion MCP Connector OAuth Routes.

Handles OAuth 2.0 + PKCE authentication for Notion's hosted MCP server.
Based on: https://developers.notion.com/guides/mcp/build-mcp-client

This creates connectors with the same ``NOTION_CONNECTOR`` type as the
existing direct-API connector, but with ``mcp_mode: True`` in the config
so the adapter layer knows to route through MCP.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.services.notion_mcp.oauth import (
    ClientCredentials,
    OAuthMetadata,
    build_authorization_url,
    discover_oauth_metadata,
    exchange_code_for_tokens,
    refresh_access_token,
    register_client,
)
from app.users import current_active_user
from app.utils.connector_naming import (
    check_duplicate_connector,
    extract_identifier_from_credentials,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption, generate_pkce_pair

logger = logging.getLogger(__name__)

router = APIRouter()

_state_manager: OAuthStateManager | None = None
_token_encryption: TokenEncryption | None = None
_oauth_metadata: OAuthMetadata | None = None


def _get_state_manager() -> OAuthStateManager:
    global _state_manager
    if _state_manager is None:
        if not config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set for OAuth security")
        _state_manager = OAuthStateManager(config.SECRET_KEY)
    return _state_manager


def _get_token_encryption() -> TokenEncryption:
    global _token_encryption
    if _token_encryption is None:
        if not config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set for token encryption")
        _token_encryption = TokenEncryption(config.SECRET_KEY)
    return _token_encryption


async def _get_oauth_metadata() -> OAuthMetadata:
    global _oauth_metadata
    if _oauth_metadata is None:
        _oauth_metadata = await discover_oauth_metadata()
    return _oauth_metadata


async def _fetch_workspace_info(access_token: str) -> dict:
    """Fetch workspace metadata using the Notion API with the fresh token.

    The ``/v1/users/me`` endpoint returns bot info including workspace_name.
    This populates connector config fields so naming and metadata services
    work correctly.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.notion.com/v1/users/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Notion-Version": "2022-06-28",
                },
            )
            if resp.is_success:
                data = resp.json()
                bot_info = data.get("bot", {})
                return {
                    "bot_id": data.get("id"),
                    "workspace_name": bot_info.get("workspace_name", "Notion Workspace"),
                    "workspace_icon": data.get("avatar_url") or "📄",
                }
    except Exception as e:
        logger.warning("Failed to fetch workspace info: %s", e)
    return {}


NOTION_MCP_REDIRECT_URI = None


def _get_redirect_uri() -> str:
    global NOTION_MCP_REDIRECT_URI
    if NOTION_MCP_REDIRECT_URI is None:
        backend = config.BACKEND_URL or "http://localhost:8000"
        NOTION_MCP_REDIRECT_URI = f"{backend}/api/v1/auth/notion-mcp/connector/callback"
    return NOTION_MCP_REDIRECT_URI


# ---------------------------------------------------------------------------
# Route: initiate OAuth
# ---------------------------------------------------------------------------


@router.get("/auth/notion-mcp/connector/add")
async def connect_notion_mcp(
    space_id: int,
    user: User = Depends(current_active_user),
):
    """Initiate Notion MCP OAuth + PKCE flow."""
    if not config.SECRET_KEY:
        raise HTTPException(status_code=500, detail="SECRET_KEY not configured.")

    try:
        metadata = await _get_oauth_metadata()

        redirect_uri = _get_redirect_uri()
        credentials = await register_client(metadata, redirect_uri)

        code_verifier, code_challenge = generate_pkce_pair()

        state_manager = _get_state_manager()
        state_encoded = state_manager.generate_secure_state(
            space_id,
            user.id,
            code_verifier=code_verifier,
            mcp_client_id=credentials.client_id,
            mcp_client_secret=credentials.client_secret or "",
        )

        auth_url = build_authorization_url(
            metadata=metadata,
            client_id=credentials.client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            state=state_encoded,
        )

        logger.info("Generated Notion MCP OAuth URL for user %s, space %s", user.id, space_id)
        return {"auth_url": auth_url}

    except Exception as e:
        logger.error("Failed to initiate Notion MCP OAuth: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Notion MCP OAuth: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Route: re-authenticate existing connector
# ---------------------------------------------------------------------------


@router.get("/auth/notion-mcp/connector/reauth")
async def reauth_notion_mcp(
    space_id: int,
    connector_id: int,
    return_url: str | None = None,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Initiate re-authentication for an existing Notion MCP connector."""
    result = await session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.search_space_id == space_id,
            SearchSourceConnector.connector_type == SearchSourceConnectorType.NOTION_CONNECTOR,
        )
    )
    connector = result.scalars().first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found or access denied")

    if not config.SECRET_KEY:
        raise HTTPException(status_code=500, detail="SECRET_KEY not configured.")

    try:
        metadata = await _get_oauth_metadata()
        redirect_uri = _get_redirect_uri()
        credentials = await register_client(metadata, redirect_uri)

        code_verifier, code_challenge = generate_pkce_pair()

        extra: dict = {
            "connector_id": connector_id,
            "code_verifier": code_verifier,
            "mcp_client_id": credentials.client_id,
            "mcp_client_secret": credentials.client_secret or "",
        }
        if return_url and return_url.startswith("/"):
            extra["return_url"] = return_url

        state_manager = _get_state_manager()
        state_encoded = state_manager.generate_secure_state(space_id, user.id, **extra)

        auth_url = build_authorization_url(
            metadata=metadata,
            client_id=credentials.client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            state=state_encoded,
        )

        logger.info("Initiating Notion MCP re-auth for user %s, connector %s", user.id, connector_id)
        return {"auth_url": auth_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to initiate Notion MCP re-auth: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate Notion MCP re-auth: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Route: OAuth callback
# ---------------------------------------------------------------------------


@router.get("/auth/notion-mcp/connector/callback")
async def notion_mcp_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    """Handle the OAuth callback from Notion's MCP authorization server."""
    if error:
        logger.warning("Notion MCP OAuth error: %s", error)
        space_id = None
        if state:
            try:
                data = _get_state_manager().validate_state(state)
                space_id = data.get("space_id")
            except Exception:
                pass
        if space_id:
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?error=notion_mcp_oauth_denied"
            )
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard?error=notion_mcp_oauth_denied"
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    state_manager = _get_state_manager()
    try:
        data = state_manager.validate_state(state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid state: {e!s}") from e

    user_id = UUID(data["user_id"])
    space_id = data["space_id"]
    code_verifier = data.get("code_verifier")
    mcp_client_id = data.get("mcp_client_id")
    mcp_client_secret = data.get("mcp_client_secret") or None

    if not code_verifier or not mcp_client_id:
        raise HTTPException(status_code=400, detail="Missing PKCE or client data in state")

    try:
        metadata = await _get_oauth_metadata()
        redirect_uri = _get_redirect_uri()

        token_set = await exchange_code_for_tokens(
            code=code,
            code_verifier=code_verifier,
            metadata=metadata,
            client_id=mcp_client_id,
            redirect_uri=redirect_uri,
            client_secret=mcp_client_secret,
        )
    except Exception as e:
        logger.error("Notion MCP token exchange failed: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e!s}") from e

    token_encryption = _get_token_encryption()

    workspace_info = await _fetch_workspace_info(token_set.access_token)

    connector_config = {
        "access_token": token_encryption.encrypt_token(token_set.access_token),
        "refresh_token": token_encryption.encrypt_token(token_set.refresh_token)
        if token_set.refresh_token
        else None,
        "expires_in": token_set.expires_in,
        "expires_at": token_set.expires_at.isoformat() if token_set.expires_at else None,
        "workspace_id": workspace_info.get("workspace_id"),
        "workspace_name": workspace_info.get("workspace_name", "Notion Workspace"),
        "workspace_icon": workspace_info.get("workspace_icon", "📄"),
        "bot_id": workspace_info.get("bot_id"),
        "mcp_mode": True,
        "mcp_client_id": mcp_client_id,
        "mcp_client_secret": token_encryption.encrypt_token(mcp_client_secret)
        if mcp_client_secret
        else None,
        "_token_encrypted": True,
    }

    reauth_connector_id = data.get("connector_id")
    reauth_return_url = data.get("return_url")

    # --- Re-auth path ---
    if reauth_connector_id:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == reauth_connector_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.connector_type == SearchSourceConnectorType.NOTION_CONNECTOR,
            )
        )
        db_connector = result.scalars().first()
        if not db_connector:
            raise HTTPException(status_code=404, detail="Connector not found during re-auth")

        db_connector.config = connector_config
        flag_modified(db_connector, "config")
        await session.commit()
        await session.refresh(db_connector)

        logger.info("Re-authenticated Notion MCP connector %s for user %s", db_connector.id, user_id)
        if reauth_return_url and reauth_return_url.startswith("/"):
            return RedirectResponse(url=f"{config.NEXT_FRONTEND_URL}{reauth_return_url}")
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?success=true&connector=notion-connector&connectorId={db_connector.id}"
        )

    # --- New connector path ---
    connector_identifier = extract_identifier_from_credentials(
        SearchSourceConnectorType.NOTION_CONNECTOR, connector_config
    )

    is_duplicate = await check_duplicate_connector(
        session,
        SearchSourceConnectorType.NOTION_CONNECTOR,
        space_id,
        user_id,
        connector_identifier,
    )
    if is_duplicate:
        logger.warning("Duplicate Notion MCP connector for user %s", user_id)
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?error=duplicate_account&connector=notion-connector"
        )

    connector_name = await generate_unique_connector_name(
        session,
        SearchSourceConnectorType.NOTION_CONNECTOR,
        space_id,
        user_id,
        connector_identifier,
    )

    new_connector = SearchSourceConnector(
        name=connector_name,
        connector_type=SearchSourceConnectorType.NOTION_CONNECTOR,
        is_indexable=True,
        config=connector_config,
        search_space_id=space_id,
        user_id=user_id,
    )
    session.add(new_connector)

    try:
        await session.commit()
        logger.info("Created Notion MCP connector for user %s in space %s", user_id, space_id)
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?success=true&connector=notion-connector&connectorId={new_connector.id}"
        )
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Database integrity error: {e!s}") from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create connector: {e!s}"
        ) from e


# ---------------------------------------------------------------------------
# Token refresh helper (used by the adapter)
# ---------------------------------------------------------------------------


async def refresh_notion_mcp_token(
    session: AsyncSession,
    connector: SearchSourceConnector,
) -> SearchSourceConnector:
    """Refresh the MCP access token for a connector.

    Handles refresh-token rotation: persists both new access_token
    and new refresh_token atomically.
    """
    token_encryption = _get_token_encryption()

    cfg = connector.config or {}
    encrypted_refresh = cfg.get("refresh_token")
    if not encrypted_refresh:
        raise HTTPException(status_code=400, detail="No refresh token available. Please re-authenticate.")

    try:
        refresh_token = token_encryption.decrypt_token(encrypted_refresh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt refresh token: {e!s}") from e

    mcp_client_id = cfg.get("mcp_client_id")
    mcp_client_secret_encrypted = cfg.get("mcp_client_secret")
    mcp_client_secret = (
        token_encryption.decrypt_token(mcp_client_secret_encrypted)
        if mcp_client_secret_encrypted
        else None
    )

    if not mcp_client_id:
        raise HTTPException(status_code=400, detail="Missing MCP client_id. Please re-authenticate.")

    metadata = await _get_oauth_metadata()

    try:
        token_set = await refresh_access_token(
            refresh_token=refresh_token,
            metadata=metadata,
            client_id=mcp_client_id,
            client_secret=mcp_client_secret,
        )
    except ValueError as e:
        if "REAUTH_REQUIRED" in str(e):
            connector.config = {**connector.config, "auth_expired": True}
            flag_modified(connector, "config")
            await session.commit()
            await session.refresh(connector)
            raise HTTPException(
                status_code=401, detail="Notion MCP authentication expired. Please re-authenticate."
            ) from e
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {e!s}") from e

    updated_config = {
        **connector.config,
        "access_token": token_encryption.encrypt_token(token_set.access_token),
        "refresh_token": token_encryption.encrypt_token(token_set.refresh_token)
        if token_set.refresh_token
        else connector.config.get("refresh_token"),
        "expires_in": token_set.expires_in,
        "expires_at": token_set.expires_at.isoformat() if token_set.expires_at else None,
        "_token_encrypted": True,
    }
    updated_config.pop("auth_expired", None)

    connector.config = updated_config
    flag_modified(connector, "config")
    await session.commit()
    await session.refresh(connector)

    logger.info("Refreshed Notion MCP token for connector %s", connector.id)
    return connector
