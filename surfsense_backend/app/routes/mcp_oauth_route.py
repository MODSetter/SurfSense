"""Generic MCP OAuth 2.1 route for services with official MCP servers.

Handles the full flow: discovery → DCR → PKCE authorization → token exchange
→ MCP_CONNECTOR creation.  Currently supports Linear, Jira, ClickUp, Slack,
and Airtable.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
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


async def _fetch_account_metadata(
    service_key: str, access_token: str, token_json: dict[str, Any],
) -> dict[str, Any]:
    """Fetch display-friendly account metadata after a successful token exchange.

    DCR services (Linear, Jira, ClickUp) issue MCP-scoped tokens that cannot
    call their standard REST/GraphQL APIs — metadata discovery for those
    happens at runtime through MCP tools instead.

    Pre-configured services (Slack, Airtable) use standard OAuth tokens that
    *can* call their APIs, so we extract metadata here.

    Failures are logged but never block connector creation.
    """
    from app.services.mcp_oauth.registry import MCP_SERVICES

    svc = MCP_SERVICES.get(service_key)
    if not svc or svc.supports_dcr:
        return {}

    import httpx

    meta: dict[str, Any] = {}

    try:
        if service_key == "slack":
            team_info = token_json.get("team", {})
            meta["team_id"] = team_info.get("id", "")
            # TODO: oauth.v2.user.access only returns team.id, not
            # team.name.  To populate team_name, add "team:read" scope
            # and call GET /api/team.info here.
            meta["team_name"] = team_info.get("name", "")
            if meta["team_name"]:
                meta["display_name"] = meta["team_name"]
            elif meta["team_id"]:
                meta["display_name"] = f"Slack ({meta['team_id']})"

        elif service_key == "airtable":
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.airtable.com/v0/meta/whoami",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Airtable whoami API response: status=%s body=%s",
                        resp.status_code, resp.text[:300],
                    )
                if resp.status_code == 200:
                    whoami = resp.json()
                    meta["user_id"] = whoami.get("id", "")
                    meta["user_email"] = whoami.get("email", "")
                    meta["display_name"] = whoami.get("email", "Airtable")

    except Exception:
        logger.warning(
            "Failed to fetch account metadata for %s (non-blocking)",
            service_key,
            exc_info=True,
        )

    return meta

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
    base = config.BACKEND_URL or "http://localhost:8000"
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
        auth_endpoint = svc.auth_endpoint_override or metadata.get("authorization_endpoint")
        token_endpoint = svc.token_endpoint_override or metadata.get("token_endpoint")
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
        elif svc.client_id_env:
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
            auth_params[svc.scope_param] = " ".join(svc.scopes)

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
            status_code=500, detail=f"Failed to initiate {service} MCP OAuth.",
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

    if svc_key != service:
        raise HTTPException(status_code=400, detail="State/path service mismatch")

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
        refresh_token = token_json.get("refresh_token")
        expires_in = token_json.get("expires_in")
        scope = token_json.get("scope")

        if not access_token and "authed_user" in token_json:
            authed = token_json["authed_user"]
            access_token = authed.get("access_token")
            refresh_token = refresh_token or authed.get("refresh_token")
            scope = scope or authed.get("scope")
            expires_in = expires_in or authed.get("expires_in")

        if not access_token:
            raise HTTPException(
                status_code=400,
                detail=f"No access token received from {svc.name}.",
            )

        expires_at = None
        if expires_in:
            expires_at = datetime.now(UTC) + timedelta(
                seconds=int(expires_in)
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
                "scope": scope,
            },
            "_token_encrypted": True,
        }

        account_meta = await _fetch_account_metadata(svc_key, access_token, token_json)
        if account_meta:
            connector_config.update(account_meta)
            logger.info(
                "Stored account metadata for %s: display_name=%s",
                svc_key, account_meta.get("display_name", ""),
            )

        # ---- Re-auth path ----
        db_connector_type = SearchSourceConnectorType(svc.connector_type)
        reauth_connector_id = data.get("connector_id")
        if reauth_connector_id:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == reauth_connector_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.search_space_id == space_id,
                    SearchSourceConnector.connector_type == db_connector_type,
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
            if reauth_return_url and reauth_return_url.startswith("/") and not reauth_return_url.startswith("//"):
                return RedirectResponse(
                    url=f"{config.NEXT_FRONTEND_URL}{reauth_return_url}"
                )
            return _frontend_redirect(
                space_id, success=True, connector_id=db_connector.id, service=service,
            )

        # ---- New connector path ----
        naming_identifier = account_meta.get("display_name")
        connector_name = await generate_unique_connector_name(
            session,
            db_connector_type,
            space_id,
            user_id,
            naming_identifier,
        )

        new_connector = SearchSourceConnector(
            name=connector_name,
            connector_type=db_connector_type,
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
                status_code=409, detail="A connector for this service already exists.",
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
            detail=f"Failed to complete {service} MCP OAuth.",
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
    from app.services.mcp_oauth.registry import get_service

    svc = get_service(service)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Unknown MCP service: {service}")

    db_connector_type = SearchSourceConnectorType(svc.connector_type)
    result = await session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.search_space_id == space_id,
            SearchSourceConnector.connector_type == db_connector_type,
        )
    )
    if not result.scalars().first():
        raise HTTPException(
            status_code=404, detail="Connector not found or access denied",
        )

    try:
        from app.services.mcp_oauth.discovery import (
            discover_oauth_metadata,
            register_client,
        )

        metadata = await discover_oauth_metadata(
            svc.mcp_url, origin_override=svc.oauth_discovery_origin,
        )
        auth_endpoint = svc.auth_endpoint_override or metadata.get("authorization_endpoint")
        token_endpoint = svc.token_endpoint_override or metadata.get("token_endpoint")
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
        elif svc.client_id_env:
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
            auth_params[svc.scope_param] = " ".join(svc.scopes)

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
            detail=f"Failed to initiate {service} MCP re-auth.",
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
