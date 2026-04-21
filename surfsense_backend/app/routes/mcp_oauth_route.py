"""Generic MCP OAuth 2.1 route for services with official MCP servers.

Handles the full flow: discovery → DCR → PKCE authorization → token exchange
→ MCP_CONNECTOR creation.  Currently supports Linear, Jira, and ClickUp.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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
from app.users import current_active_user
from app.utils.connector_naming import generate_unique_connector_name
from app.utils.oauth_security import OAuthStateManager, TokenEncryption, generate_pkce_pair

logger = logging.getLogger(__name__)

router = APIRouter()

_state_manager: OAuthStateManager | None = None
_token_encryption: TokenEncryption | None = None


def _get_state_manager() -> OAuthStateManager:
    global _state_manager
    if _state_manager is None:
        if not config.SECRET_KEY:
            raise HTTPException(status_code=500, detail="SECRET_KEY not configured.")
        _state_manager = OAuthStateManager(config.SECRET_KEY)
    return _state_manager


def _get_token_encryption() -> TokenEncryption:
    global _token_encryption
    if _token_encryption is None:
        if not config.SECRET_KEY:
            raise HTTPException(status_code=500, detail="SECRET_KEY not configured.")
        _token_encryption = TokenEncryption(config.SECRET_KEY)
    return _token_encryption


def _build_redirect_uri(service: str) -> str:
    base = config.BACKEND_URL
    if not base:
        raise HTTPException(status_code=500, detail="BACKEND_URL not configured.")
    return f"{base.rstrip('/')}/api/v1/auth/mcp/{service}/connector/callback"


def _frontend_redirect(
    space_id: int | None,
    *,
    success: bool = False,
    connector_id: int | None = None,
    error: str | None = None,
    service: str = "mcp",
) -> RedirectResponse:
    if success and space_id:
        qs = f"success=true&connector={service}-mcp-connector"
        if connector_id:
            qs += f"&connectorId={connector_id}"
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?{qs}"
        )
    if error and space_id:
        return RedirectResponse(
            url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?error={error}"
        )
    return RedirectResponse(url=f"{config.NEXT_FRONTEND_URL}/dashboard")


# ---------------------------------------------------------------------------
# /add — start MCP OAuth flow
# ---------------------------------------------------------------------------

@router.get("/auth/mcp/{service}/connector/add")
async def connect_mcp_service(
    service: str,
    space_id: int,
    user: User = Depends(current_active_user),
):
    from app.services.mcp_oauth.registry import get_service

    svc = get_service(service)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Unknown MCP service: {service}")

    try:
        from app.services.mcp_oauth.discovery import (
            discover_oauth_metadata,
            register_client,
        )

        metadata = await discover_oauth_metadata(
            svc.mcp_url, origin_override=svc.oauth_discovery_origin,
        )
        auth_endpoint = metadata.get("authorization_endpoint")
        token_endpoint = metadata.get("token_endpoint")
        registration_endpoint = metadata.get("registration_endpoint")

        if not auth_endpoint or not token_endpoint:
            raise HTTPException(
                status_code=502,
                detail=f"{svc.name} MCP server returned incomplete OAuth metadata.",
            )

        redirect_uri = _build_redirect_uri(service)

        if svc.supports_dcr and registration_endpoint:
            dcr = await register_client(registration_endpoint, redirect_uri)
            client_id = dcr.get("client_id")
            client_secret = dcr.get("client_secret", "")
            if not client_id:
                raise HTTPException(
                    status_code=502,
                    detail=f"DCR for {svc.name} did not return a client_id.",
                )
        elif not svc.supports_dcr and svc.client_id_env:
            client_id = getattr(config, svc.client_id_env, None)
            client_secret = getattr(config, svc.client_secret_env or "", None) or ""
            if not client_id:
                raise HTTPException(
                    status_code=500,
                    detail=f"{svc.name} MCP OAuth not configured ({svc.client_id_env}).",
                )
        else:
            raise HTTPException(
                status_code=502,
                detail=f"{svc.name} MCP server has no DCR and no fallback credentials.",
            )

        verifier, challenge = generate_pkce_pair()
        enc = _get_token_encryption()

        state = _get_state_manager().generate_secure_state(
            space_id,
            user.id,
            service=service,
            code_verifier=verifier,
            mcp_client_id=client_id,
            mcp_client_secret=enc.encrypt_token(client_secret) if client_secret else "",
            mcp_token_endpoint=token_endpoint,
            mcp_url=svc.mcp_url,
        )

        auth_params: dict[str, str] = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        if svc.scopes:
            auth_params["scope"] = " ".join(svc.scopes)

        auth_url = f"{auth_endpoint}?{urlencode(auth_params)}"

        logger.info(
            "Generated %s MCP OAuth URL for user %s, space %s",
            svc.name, user.id, space_id,
        )
        return {"auth_url": auth_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to initiate %s MCP OAuth: %s", service, e, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate {service} MCP OAuth: {e!s}",
        ) from e


# ---------------------------------------------------------------------------
# /callback — handle OAuth redirect
# ---------------------------------------------------------------------------

@router.get("/auth/mcp/{service}/connector/callback")
async def mcp_oauth_callback(
    service: str,
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    if error:
        logger.warning("%s MCP OAuth error: %s", service, error)
        space_id = None
        if state:
            try:
                data = _get_state_manager().validate_state(state)
                space_id = data.get("space_id")
            except Exception:
                pass
        return _frontend_redirect(
            space_id, error=f"{service}_mcp_oauth_denied", service=service,
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    data = _get_state_manager().validate_state(state)
    user_id = UUID(data["user_id"])
    space_id = data["space_id"]
    svc_key = data.get("service", service)

    from app.services.mcp_oauth.registry import get_service

    svc = get_service(svc_key)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Unknown MCP service: {svc_key}")

    try:
        from app.services.mcp_oauth.discovery import exchange_code_for_tokens

        enc = _get_token_encryption()
        client_id = data["mcp_client_id"]
        client_secret = (
            enc.decrypt_token(data["mcp_client_secret"])
            if data.get("mcp_client_secret")
            else ""
        )
        token_endpoint = data["mcp_token_endpoint"]
        code_verifier = data["code_verifier"]
        mcp_url = data["mcp_url"]
        redirect_uri = _build_redirect_uri(service)

        token_json = await exchange_code_for_tokens(
            token_endpoint=token_endpoint,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            code_verifier=code_verifier,
        )

        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail=f"No access token received from {svc.name}.",
            )

        refresh_token = token_json.get("refresh_token")
        expires_at = None
        if token_json.get("expires_in"):
            expires_at = datetime.now(UTC) + timedelta(
                seconds=int(token_json["expires_in"])
            )

        connector_config = {
            "server_config": {
                "transport": "streamable-http",
                "url": mcp_url,
                "headers": {"Authorization": f"Bearer {access_token}"},
            },
            "mcp_service": svc_key,
            "mcp_oauth": {
                "client_id": client_id,
                "client_secret": enc.encrypt_token(client_secret) if client_secret else "",
                "token_endpoint": token_endpoint,
                "access_token": enc.encrypt_token(access_token),
                "refresh_token": enc.encrypt_token(refresh_token) if refresh_token else None,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "scope": token_json.get("scope"),
            },
            "_token_encrypted": True,
        }

        # ---- Re-auth path ----
        reauth_connector_id = data.get("connector_id")
        if reauth_connector_id:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == reauth_connector_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.search_space_id == space_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.MCP_CONNECTOR,
                )
            )
            db_connector = result.scalars().first()
            if not db_connector:
                raise HTTPException(
                    status_code=404,
                    detail="Connector not found during re-auth",
                )

            db_connector.config = connector_config
            flag_modified(db_connector, "config")
            await session.commit()
            await session.refresh(db_connector)

            _invalidate_cache(space_id)

            logger.info(
                "Re-authenticated %s MCP connector %s for user %s",
                svc.name, db_connector.id, user_id,
            )
            reauth_return_url = data.get("return_url")
            if reauth_return_url and reauth_return_url.startswith("/"):
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}{reauth_return_url}"
                )
            return _frontend_redirect(
                space_id, success=True, connector_id=db_connector.id, service=service,
            )

        # ---- New connector path ----
        connector_name = await generate_unique_connector_name(
            session,
            SearchSourceConnectorType.MCP_CONNECTOR,
            space_id,
            user_id,
            f"{svc.name} MCP",
        )

        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=SearchSourceConnectorType.MCP_CONNECTOR,
            is_indexable=False,
            config=connector_config,
            search_space_id=space_id,
            user_id=user_id,
        )
        session.add(new_connector)

        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(
                status_code=409, detail=f"Database integrity error: {e!s}",
            ) from e

        _invalidate_cache(space_id)

        logger.info(
            "Created %s MCP connector %s for user %s in space %s",
            svc.name, new_connector.id, user_id, space_id,
        )
        return _frontend_redirect(
            space_id, success=True, connector_id=new_connector.id, service=service,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to complete %s MCP OAuth: %s", service, e, exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete {service} MCP OAuth: {e!s}",
        ) from e


# ---------------------------------------------------------------------------
# /reauth — re-authenticate an existing MCP connector
# ---------------------------------------------------------------------------

@router.get("/auth/mcp/{service}/connector/reauth")
async def reauth_mcp_service(
    service: str,
    space_id: int,
    connector_id: int,
    return_url: str | None = None,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.search_space_id == space_id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.MCP_CONNECTOR,
        )
    )
    if not result.scalars().first():
        raise HTTPException(
            status_code=404, detail="MCP connector not found or access denied",
        )

    from app.services.mcp_oauth.registry import get_service

    svc = get_service(service)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Unknown MCP service: {service}")

    try:
        from app.services.mcp_oauth.discovery import (
            discover_oauth_metadata,
            register_client,
        )

        metadata = await discover_oauth_metadata(
            svc.mcp_url, origin_override=svc.oauth_discovery_origin,
        )
        auth_endpoint = metadata.get("authorization_endpoint")
        token_endpoint = metadata.get("token_endpoint")
        registration_endpoint = metadata.get("registration_endpoint")

        if not auth_endpoint or not token_endpoint:
            raise HTTPException(
                status_code=502,
                detail=f"{svc.name} MCP server returned incomplete OAuth metadata.",
            )

        redirect_uri = _build_redirect_uri(service)

        if svc.supports_dcr and registration_endpoint:
            dcr = await register_client(registration_endpoint, redirect_uri)
            client_id = dcr.get("client_id")
            client_secret = dcr.get("client_secret", "")
            if not client_id:
                raise HTTPException(
                    status_code=502,
                    detail=f"DCR for {svc.name} did not return a client_id.",
                )
        elif not svc.supports_dcr and svc.client_id_env:
            client_id = getattr(config, svc.client_id_env, None)
            client_secret = getattr(config, svc.client_secret_env or "", None) or ""
            if not client_id:
                raise HTTPException(
                    status_code=500,
                    detail=f"{svc.name} MCP OAuth not configured ({svc.client_id_env}).",
                )
        else:
            raise HTTPException(
                status_code=502,
                detail=f"{svc.name} MCP server has no DCR and no fallback credentials.",
            )

        verifier, challenge = generate_pkce_pair()
        enc = _get_token_encryption()

        extra: dict = {
            "service": service,
            "code_verifier": verifier,
            "mcp_client_id": client_id,
            "mcp_client_secret": enc.encrypt_token(client_secret) if client_secret else "",
            "mcp_token_endpoint": token_endpoint,
            "mcp_url": svc.mcp_url,
            "connector_id": connector_id,
        }
        if return_url and return_url.startswith("/"):
            extra["return_url"] = return_url

        state = _get_state_manager().generate_secure_state(
            space_id, user.id, **extra,
        )

        auth_params: dict[str, str] = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        if svc.scopes:
            auth_params["scope"] = " ".join(svc.scopes)

        auth_url = f"{auth_endpoint}?{urlencode(auth_params)}"

        logger.info(
            "Initiating %s MCP re-auth for user %s, connector %s",
            svc.name, user.id, connector_id,
        )
        return {"auth_url": auth_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to initiate %s MCP re-auth: %s", service, e, exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate {service} MCP re-auth: {e!s}",
        ) from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invalidate_cache(space_id: int) -> None:
    try:
        from app.agents.new_chat.tools.mcp_tool import invalidate_mcp_tools_cache

        invalidate_mcp_tools_cache(space_id)
    except Exception:
        logger.debug("MCP cache invalidation skipped", exc_info=True)
