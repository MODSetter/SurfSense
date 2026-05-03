"""Reusable base for OAuth 2.0 connector routes.

Subclasses override ``fetch_account_info``, ``build_connector_config``,
and ``get_connector_display_name`` to customise provider-specific behaviour.
Call ``build_router()`` to get a FastAPI ``APIRouter`` with ``/connector/add``,
``/connector/callback``, and ``/connector/reauth`` endpoints.
"""

from __future__ import annotations

import base64
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
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
from app.utils.connector_naming import (
    check_duplicate_connector,
    generate_unique_connector_name,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)


class OAuthConnectorRoute:
    def __init__(
        self,
        *,
        provider_name: str,
        connector_type: SearchSourceConnectorType,
        authorize_url: str,
        token_url: str,
        client_id_env: str,
        client_secret_env: str,
        redirect_uri_env: str,
        scopes: list[str],
        auth_prefix: str,
        use_pkce: bool = False,
        token_auth_method: str = "body",
        is_indexable: bool = True,
        extra_auth_params: dict[str, str] | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.connector_type = connector_type
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.client_id_env = client_id_env
        self.client_secret_env = client_secret_env
        self.redirect_uri_env = redirect_uri_env
        self.scopes = scopes
        self.auth_prefix = auth_prefix.rstrip("/")
        self.use_pkce = use_pkce
        self.token_auth_method = token_auth_method
        self.is_indexable = is_indexable
        self.extra_auth_params = extra_auth_params or {}

        self._state_manager: OAuthStateManager | None = None
        self._token_encryption: TokenEncryption | None = None

    def _get_client_id(self) -> str:
        value = getattr(config, self.client_id_env, None)
        if not value:
            raise HTTPException(
                status_code=500,
                detail=f"{self.provider_name.title()} OAuth not configured "
                f"({self.client_id_env} missing).",
            )
        return value

    def _get_client_secret(self) -> str:
        value = getattr(config, self.client_secret_env, None)
        if not value:
            raise HTTPException(
                status_code=500,
                detail=f"{self.provider_name.title()} OAuth not configured "
                f"({self.client_secret_env} missing).",
            )
        return value

    def _get_redirect_uri(self) -> str:
        value = getattr(config, self.redirect_uri_env, None)
        if not value:
            raise HTTPException(
                status_code=500,
                detail=f"{self.redirect_uri_env} not configured.",
            )
        return value

    def _get_state_manager(self) -> OAuthStateManager:
        if self._state_manager is None:
            if not config.SECRET_KEY:
                raise HTTPException(
                    status_code=500,
                    detail="SECRET_KEY not configured for OAuth security.",
                )
            self._state_manager = OAuthStateManager(config.SECRET_KEY)
        return self._state_manager

    def _get_token_encryption(self) -> TokenEncryption:
        if self._token_encryption is None:
            if not config.SECRET_KEY:
                raise HTTPException(
                    status_code=500,
                    detail="SECRET_KEY not configured for token encryption.",
                )
            self._token_encryption = TokenEncryption(config.SECRET_KEY)
        return self._token_encryption

    def _frontend_redirect(
        self,
        space_id: int | None,
        *,
        success: bool = False,
        connector_id: int | None = None,
        error: str | None = None,
    ) -> RedirectResponse:
        if success and space_id:
            connector_slug = f"{self.provider_name}-connector"
            qs = f"success=true&connector={connector_slug}"
            if connector_id:
                qs += f"&connectorId={connector_id}"
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?{qs}"
            )
        if error and space_id:
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/connectors/callback?error={error}"
            )
        if error:
            return RedirectResponse(
                url=f"{config.NEXT_FRONTEND_URL}/dashboard?error={error}"
            )
        return RedirectResponse(url=f"{config.NEXT_FRONTEND_URL}/dashboard")

    async def fetch_account_info(self, access_token: str) -> dict[str, Any]:
        """Override to fetch account/workspace info after token exchange.

        Return dict is merged into connector config; key ``"name"`` is used
        for the display name and dedup.
        """
        return {}

    def build_connector_config(
        self,
        token_json: dict[str, Any],
        account_info: dict[str, Any],
        encryption: TokenEncryption,
    ) -> dict[str, Any]:
        """Override for custom config shapes. Default: standard encrypted OAuth fields."""
        access_token = token_json.get("access_token", "")
        refresh_token = token_json.get("refresh_token")

        expires_at = None
        if token_json.get("expires_in"):
            expires_at = datetime.now(UTC) + timedelta(
                seconds=int(token_json["expires_in"])
            )

        cfg: dict[str, Any] = {
            "access_token": encryption.encrypt_token(access_token),
            "refresh_token": (
                encryption.encrypt_token(refresh_token) if refresh_token else None
            ),
            "token_type": token_json.get("token_type", "Bearer"),
            "expires_in": token_json.get("expires_in"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": token_json.get("scope"),
            "_token_encrypted": True,
        }
        cfg.update(account_info)
        return cfg

    def get_connector_display_name(self, account_info: dict[str, Any]) -> str:
        return str(account_info.get("name", self.provider_name.title()))

    async def on_token_refresh_failure(
        self,
        session: AsyncSession,
        connector: SearchSourceConnector,
    ) -> None:
        try:
            connector.config = {**connector.config, "auth_expired": True}
            flag_modified(connector, "config")
            await session.commit()
            await session.refresh(connector)
        except Exception:
            logger.warning(
                "Failed to persist auth_expired flag for connector %s",
                connector.id,
                exc_info=True,
            )

    async def _exchange_code(
        self, code: str, extra_state: dict[str, Any]
    ) -> dict[str, Any]:
        client_id = self._get_client_id()
        client_secret = self._get_client_secret()
        redirect_uri = self._get_redirect_uri()

        headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }

        if self.token_auth_method == "basic":
            creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"
        else:
            body["client_id"] = client_id
            body["client_secret"] = client_secret

        if self.use_pkce:
            verifier = extra_state.get("code_verifier")
            if verifier:
                body["code_verifier"] = verifier

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.token_url, data=body, headers=headers, timeout=30.0
            )

        if resp.status_code != 200:
            detail = resp.text
            with contextlib.suppress(Exception):
                detail = resp.json().get("error_description", detail)
            raise HTTPException(
                status_code=400, detail=f"Token exchange failed: {detail}"
            )

        return resp.json()

    async def refresh_token(
        self, session: AsyncSession, connector: SearchSourceConnector
    ) -> SearchSourceConnector:
        encryption = self._get_token_encryption()
        is_encrypted = connector.config.get("_token_encrypted", False)

        refresh_tok = connector.config.get("refresh_token")
        if is_encrypted and refresh_tok:
            try:
                refresh_tok = encryption.decrypt_token(refresh_tok)
            except Exception as e:
                logger.error("Failed to decrypt refresh token: %s", e)
                raise HTTPException(
                    status_code=500, detail="Failed to decrypt stored refresh token"
                ) from e

        if not refresh_tok:
            await self.on_token_refresh_failure(session, connector)
            raise HTTPException(
                status_code=400,
                detail="No refresh token available. Please re-authenticate.",
            )

        client_id = self._get_client_id()
        client_secret = self._get_client_secret()

        headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
        }

        if self.token_auth_method == "basic":
            creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"
        else:
            body["client_id"] = client_id
            body["client_secret"] = client_secret

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.token_url, data=body, headers=headers, timeout=30.0
            )

        if resp.status_code != 200:
            error_detail = resp.text
            try:
                ej = resp.json()
                error_detail = ej.get("error_description", error_detail)
                error_code = ej.get("error", "")
            except Exception:
                error_code = ""
            combined = (error_detail + error_code).lower()
            if any(kw in combined for kw in ("invalid_grant", "expired", "revoked")):
                await self.on_token_refresh_failure(session, connector)
                raise HTTPException(
                    status_code=401,
                    detail=f"{self.provider_name.title()} authentication failed. "
                    "Please re-authenticate.",
                )
            raise HTTPException(
                status_code=400, detail=f"Token refresh failed: {error_detail}"
            )

        token_json = resp.json()
        new_access = token_json.get("access_token")
        if not new_access:
            raise HTTPException(
                status_code=400, detail="No access token received from refresh"
            )

        expires_at = None
        if token_json.get("expires_in"):
            expires_at = datetime.now(UTC) + timedelta(
                seconds=int(token_json["expires_in"])
            )

        updated_config = dict(connector.config)
        updated_config["access_token"] = encryption.encrypt_token(new_access)
        new_refresh = token_json.get("refresh_token")
        if new_refresh:
            updated_config["refresh_token"] = encryption.encrypt_token(new_refresh)
        updated_config["expires_in"] = token_json.get("expires_in")
        updated_config["expires_at"] = expires_at.isoformat() if expires_at else None
        updated_config["scope"] = token_json.get("scope", updated_config.get("scope"))
        updated_config["_token_encrypted"] = True
        updated_config.pop("auth_expired", None)

        connector.config = updated_config
        flag_modified(connector, "config")
        await session.commit()
        await session.refresh(connector)

        logger.info(
            "Refreshed %s token for connector %s",
            self.provider_name,
            connector.id,
        )
        return connector

    def build_router(self) -> APIRouter:
        router = APIRouter()
        oauth = self

        @router.get(f"{oauth.auth_prefix}/connector/add")
        async def connect(
            space_id: int,
            user: User = Depends(current_active_user),
        ):
            if not space_id:
                raise HTTPException(status_code=400, detail="space_id is required")

            client_id = oauth._get_client_id()
            state_mgr = oauth._get_state_manager()

            extra_state: dict[str, Any] = {}
            auth_params: dict[str, str] = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": oauth._get_redirect_uri(),
                "scope": " ".join(oauth.scopes),
            }

            if oauth.use_pkce:
                from app.utils.oauth_security import generate_pkce_pair

                verifier, challenge = generate_pkce_pair()
                extra_state["code_verifier"] = verifier
                auth_params["code_challenge"] = challenge
                auth_params["code_challenge_method"] = "S256"

            auth_params.update(oauth.extra_auth_params)

            state_encoded = state_mgr.generate_secure_state(
                space_id, user.id, **extra_state
            )
            auth_params["state"] = state_encoded
            auth_url = f"{oauth.authorize_url}?{urlencode(auth_params)}"

            logger.info(
                "Generated %s OAuth URL for user %s, space %s",
                oauth.provider_name,
                user.id,
                space_id,
            )
            return {"auth_url": auth_url}

        @router.get(f"{oauth.auth_prefix}/connector/reauth")
        async def reauth(
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
                    SearchSourceConnector.connector_type == oauth.connector_type,
                )
            )
            if not result.scalars().first():
                raise HTTPException(
                    status_code=404,
                    detail=f"{oauth.provider_name.title()} connector not found "
                    "or access denied",
                )

            client_id = oauth._get_client_id()
            state_mgr = oauth._get_state_manager()

            extra: dict[str, Any] = {"connector_id": connector_id}
            if (
                return_url
                and return_url.startswith("/")
                and not return_url.startswith("//")
            ):
                extra["return_url"] = return_url

            auth_params: dict[str, str] = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": oauth._get_redirect_uri(),
                "scope": " ".join(oauth.scopes),
            }

            if oauth.use_pkce:
                from app.utils.oauth_security import generate_pkce_pair

                verifier, challenge = generate_pkce_pair()
                extra["code_verifier"] = verifier
                auth_params["code_challenge"] = challenge
                auth_params["code_challenge_method"] = "S256"

            auth_params.update(oauth.extra_auth_params)

            state_encoded = state_mgr.generate_secure_state(space_id, user.id, **extra)
            auth_params["state"] = state_encoded
            auth_url = f"{oauth.authorize_url}?{urlencode(auth_params)}"

            logger.info(
                "Initiating %s re-auth for user %s, connector %s",
                oauth.provider_name,
                user.id,
                connector_id,
            )
            return {"auth_url": auth_url}

        @router.get(f"{oauth.auth_prefix}/connector/callback")
        async def callback(
            code: str | None = None,
            error: str | None = None,
            state: str | None = None,
            session: AsyncSession = Depends(get_async_session),
        ):
            error_label = f"{oauth.provider_name}_oauth_denied"

            if error:
                logger.warning("%s OAuth error: %s", oauth.provider_name, error)
                space_id = None
                if state:
                    try:
                        data = oauth._get_state_manager().validate_state(state)
                        space_id = data.get("space_id")
                    except Exception:
                        pass
                return oauth._frontend_redirect(space_id, error=error_label)

            if not code:
                raise HTTPException(
                    status_code=400, detail="Missing authorization code"
                )
            if not state:
                raise HTTPException(status_code=400, detail="Missing state parameter")

            state_mgr = oauth._get_state_manager()
            try:
                data = state_mgr.validate_state(state)
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail="Invalid or expired state parameter."
                ) from e

            user_id = UUID(data["user_id"])
            space_id = data["space_id"]

            token_json = await oauth._exchange_code(code, data)

            access_token = token_json.get("access_token", "")
            if not access_token:
                raise HTTPException(
                    status_code=400,
                    detail=f"No access token received from {oauth.provider_name.title()}",
                )

            account_info = await oauth.fetch_account_info(access_token)
            encryption = oauth._get_token_encryption()
            connector_config = oauth.build_connector_config(
                token_json, account_info, encryption
            )

            display_name = oauth.get_connector_display_name(account_info)

            # --- Re-auth path ---
            reauth_connector_id = data.get("connector_id")
            reauth_return_url = data.get("return_url")

            if reauth_connector_id:
                result = await session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == reauth_connector_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.search_space_id == space_id,
                        SearchSourceConnector.connector_type == oauth.connector_type,
                    )
                )
                db_connector = result.scalars().first()
                if not db_connector:
                    raise HTTPException(
                        status_code=404,
                        detail="Connector not found or access denied during re-auth",
                    )

                db_connector.config = connector_config
                flag_modified(db_connector, "config")
                await session.commit()
                await session.refresh(db_connector)

                logger.info(
                    "Re-authenticated %s connector %s for user %s",
                    oauth.provider_name,
                    db_connector.id,
                    user_id,
                )
                if (
                    reauth_return_url
                    and reauth_return_url.startswith("/")
                    and not reauth_return_url.startswith("//")
                ):
                    return RedirectResponse(
                        url=f"{config.NEXT_FRONTEND_URL}{reauth_return_url}"
                    )
                return oauth._frontend_redirect(
                    space_id, success=True, connector_id=db_connector.id
                )

            # --- New connector path ---
            is_dup = await check_duplicate_connector(
                session,
                oauth.connector_type,
                space_id,
                user_id,
                display_name,
            )
            if is_dup:
                logger.warning(
                    "Duplicate %s connector for user %s (%s)",
                    oauth.provider_name,
                    user_id,
                    display_name,
                )
                return oauth._frontend_redirect(
                    space_id,
                    error=f"duplicate_account&connector={oauth.provider_name}-connector",
                )

            connector_name = await generate_unique_connector_name(
                session,
                oauth.connector_type,
                space_id,
                user_id,
                display_name,
            )

            new_connector = SearchSourceConnector(
                name=connector_name,
                connector_type=oauth.connector_type,
                is_indexable=oauth.is_indexable,
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
                    status_code=409,
                    detail="A connector for this service already exists.",
                ) from e

            logger.info(
                "Created %s connector %s for user %s in space %s",
                oauth.provider_name,
                new_connector.id,
                user_id,
                space_id,
            )
            return oauth._frontend_redirect(
                space_id, success=True, connector_id=new_connector.id
            )

        return router
