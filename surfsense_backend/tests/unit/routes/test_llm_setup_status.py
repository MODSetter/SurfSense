"""Unit tests for the server-authoritative LLM onboarding verdict.

``compute_llm_setup_status`` is the single source of truth for whether a
workspace can chat. These tests cover the two pieces of genuinely new logic:

1. ``_global_catalog_has_usable_chat`` — a pure check over the operator
   global catalog (usable model, not mere file presence).
2. The decision tree in ``compute_llm_setup_status`` — exercised by faking
   the DB-touching seams (``_clear_invalid_roles`` heals dangling pins,
   ``_workspace_has_enabled_chat_model`` reports BYOK models) so the routing
   between ready / needs_setup / global_config / models is asserted directly.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from app.auth.context import AuthContext
from app.db import Permission
from app.routes import model_connections_routes as mc


@dataclass
class _FakeUser:
    id: str = "u1"


@dataclass
class _FakeWorkspace:
    chat_model_id: int | None = 0
    vision_model_id: int | None = 0
    image_gen_model_id: int | None = 0


def _global_model(
    *,
    model_id: int = -1,
    connection_id: int = -1,
    enabled: bool = True,
    supports_chat: bool = True,
) -> dict:
    return {
        "id": model_id,
        "connection_id": connection_id,
        "enabled": enabled,
        "supports_chat": supports_chat,
        "capabilities_override": {},
    }


class TestGlobalCatalogHasUsableChat:
    """Usability, not file existence, is what counts."""

    def test_usable_when_enabled_connection_and_chat_model(self, monkeypatch):
        monkeypatch.setattr(mc.config, "GLOBAL_CONNECTIONS", [{"id": -1, "enabled": True}])
        monkeypatch.setattr(mc.config, "GLOBAL_MODELS", [_global_model()])
        assert mc._global_catalog_has_usable_chat() is True

    def test_empty_catalog_is_not_usable(self, monkeypatch):
        monkeypatch.setattr(mc.config, "GLOBAL_CONNECTIONS", [])
        monkeypatch.setattr(mc.config, "GLOBAL_MODELS", [])
        assert mc._global_catalog_has_usable_chat() is False

    def test_disabled_connection_is_not_usable(self, monkeypatch):
        monkeypatch.setattr(mc.config, "GLOBAL_CONNECTIONS", [{"id": -1, "enabled": False}])
        monkeypatch.setattr(mc.config, "GLOBAL_MODELS", [_global_model()])
        assert mc._global_catalog_has_usable_chat() is False

    def test_disabled_model_is_not_usable(self, monkeypatch):
        monkeypatch.setattr(mc.config, "GLOBAL_CONNECTIONS", [{"id": -1, "enabled": True}])
        monkeypatch.setattr(mc.config, "GLOBAL_MODELS", [_global_model(enabled=False)])
        assert mc._global_catalog_has_usable_chat() is False

    def test_non_chat_model_is_not_usable(self, monkeypatch):
        monkeypatch.setattr(mc.config, "GLOBAL_CONNECTIONS", [{"id": -1, "enabled": True}])
        monkeypatch.setattr(
            mc.config, "GLOBAL_MODELS", [_global_model(supports_chat=False)]
        )
        assert mc._global_catalog_has_usable_chat() is False


async def _run_status(
    *,
    file_exists: bool,
    global_usable: bool,
    chat_model_id: int,
    ws_has_chat: bool = False,
    permissions: list[str] | None = None,
):
    """Drive the decision tree with DB-touching seams stubbed out."""
    if permissions is None:
        permissions = [Permission.FULL_ACCESS.value]
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(mc.config, "GLOBAL_LLM_CONFIG_FILE_EXISTS", file_exists)
        )
        stack.enter_context(
            patch.object(
                mc, "_global_catalog_has_usable_chat", return_value=global_usable
            )
        )
        stack.enter_context(patch.object(mc, "check_permission", AsyncMock()))
        stack.enter_context(
            patch.object(
                mc, "get_user_permissions", AsyncMock(return_value=permissions)
            )
        )
        stack.enter_context(
            patch.object(
                mc,
                "_clear_invalid_roles",
                AsyncMock(return_value=_FakeWorkspace(chat_model_id=chat_model_id)),
            )
        )
        stack.enter_context(
            patch.object(
                mc,
                "_workspace_has_enabled_chat_model",
                AsyncMock(return_value=ws_has_chat),
            )
        )
        return await mc.compute_llm_setup_status(
            AsyncMock(), AuthContext.session(_FakeUser()), 1
        )


class TestComputeLlmSetupStatus:
    @pytest.mark.asyncio
    async def test_no_yaml_no_models_needs_setup(self):
        result = await _run_status(
            file_exists=False, global_usable=False, chat_model_id=0, ws_has_chat=False
        )
        assert result.status == "needs_setup"
        assert result.source == "none"

    @pytest.mark.asyncio
    async def test_usable_global_catalog_is_ready(self):
        result = await _run_status(
            file_exists=True, global_usable=True, chat_model_id=0
        )
        assert result.status == "ready"
        assert result.source == "global_config"

    @pytest.mark.asyncio
    async def test_yaml_present_but_empty_catalog_falls_through(self):
        # File exists but no usable model AND no BYOK => onboarding, not a
        # dead composer. This is the empty/broken-YAML regression.
        result = await _run_status(
            file_exists=True, global_usable=False, chat_model_id=0, ws_has_chat=False
        )
        assert result.status == "needs_setup"
        assert result.source == "none"

    @pytest.mark.asyncio
    async def test_auto_mode_with_workspace_model_is_ready(self):
        result = await _run_status(
            file_exists=False, global_usable=False, chat_model_id=0, ws_has_chat=True
        )
        assert result.status == "ready"
        assert result.source == "models"

    @pytest.mark.asyncio
    async def test_auto_mode_counts_global_catalog_without_file(self):
        result = await _run_status(
            file_exists=False, global_usable=True, chat_model_id=0, ws_has_chat=False
        )
        assert result.status == "ready"
        assert result.source == "global_config"

    @pytest.mark.asyncio
    async def test_pinned_workspace_model_is_ready(self):
        # chat_model_id > 0 survived _clear_invalid_roles => valid + enabled.
        result = await _run_status(
            file_exists=False, global_usable=False, chat_model_id=5
        )
        assert result.status == "ready"
        assert result.source == "models"

    @pytest.mark.asyncio
    async def test_pinned_global_model_is_ready(self):
        result = await _run_status(
            file_exists=False, global_usable=False, chat_model_id=-3
        )
        assert result.status == "ready"
        assert result.source == "global_config"

    @pytest.mark.asyncio
    async def test_pinned_dead_model_healed_to_needs_setup(self):
        # A pin to a deleted/disabled model collapses to 0 in
        # _clear_invalid_roles; with no fallback model it is needs_setup.
        result = await _run_status(
            file_exists=False, global_usable=False, chat_model_id=0, ws_has_chat=False
        )
        assert result.status == "needs_setup"

    @pytest.mark.asyncio
    async def test_can_configure_owner(self):
        result = await _run_status(
            file_exists=True,
            global_usable=True,
            chat_model_id=0,
            permissions=[Permission.FULL_ACCESS.value],
        )
        assert result.can_configure is True

    @pytest.mark.asyncio
    async def test_can_configure_editor(self):
        result = await _run_status(
            file_exists=True,
            global_usable=True,
            chat_model_id=0,
            permissions=[
                Permission.LLM_CONFIGS_CREATE.value,
                Permission.LLM_CONFIGS_READ.value,
            ],
        )
        assert result.can_configure is True

    @pytest.mark.asyncio
    async def test_can_configure_viewer_is_false(self):
        result = await _run_status(
            file_exists=True,
            global_usable=True,
            chat_model_id=0,
            permissions=[Permission.LLM_CONFIGS_READ.value],
        )
        assert result.can_configure is False
