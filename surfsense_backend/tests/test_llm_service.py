"""
Tests for the LLM service module.

These tests validate:
1. LLM role constants have correct values (used for routing)
2. Global vs user-space LLM config lookup is correct
3. Missing LLMs are handled gracefully (return None, not crash)
4. Role-to-LLM mapping is correct (fast -> fast_llm_id, etc.)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Skip these tests if app dependencies aren't installed
pytest.importorskip("litellm")

from app.services.llm_service import (
    LLMRole,
    get_global_llm_config,
    get_fast_llm,
    get_long_context_llm,
    get_strategic_llm,
    get_search_space_llm_instance,
)


class TestLLMRoleConstants:
    """
    Tests for LLMRole constants.
    These values are used for database lookups and must be stable.
    """

    def test_role_constants_are_strings(self):
        """LLM role values must be strings for database compatibility."""
        assert isinstance(LLMRole.LONG_CONTEXT, str)
        assert isinstance(LLMRole.FAST, str)
        assert isinstance(LLMRole.STRATEGIC, str)

    def test_role_values_are_unique(self):
        """Role values must be unique to prevent routing confusion."""
        roles = [LLMRole.LONG_CONTEXT, LLMRole.FAST, LLMRole.STRATEGIC]
        assert len(roles) == len(set(roles))

    def test_expected_role_values(self):
        """
        Validate exact role values.
        These are used in the database schema and must not change.
        """
        assert LLMRole.LONG_CONTEXT == "long_context"
        assert LLMRole.FAST == "fast"
        assert LLMRole.STRATEGIC == "strategic"


class TestGlobalLLMConfigLookup:
    """
    Tests validating global (negative ID) LLM config lookup behavior.
    """

    def test_positive_id_never_returns_global_config(self):
        """
        Positive IDs are user-space configs, must never match global.
        Returning a global config for a user ID would be a security issue.
        """
        result = get_global_llm_config(1)
        assert result is None

        result = get_global_llm_config(100)
        assert result is None

        result = get_global_llm_config(999999)
        assert result is None

    def test_zero_id_never_returns_global_config(self):
        """Zero is not a valid global config ID."""
        result = get_global_llm_config(0)
        assert result is None

    @patch("app.services.llm_service.config")
    def test_negative_id_matches_correct_global_config(self, mock_config):
        """
        Negative IDs should match global configs by exact ID.
        Wrong matching would return wrong model configuration.
        """
        mock_config.GLOBAL_LLM_CONFIGS = [
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-4"},
            {"id": -2, "provider": "ANTHROPIC", "model_name": "claude-3"},
            {"id": -3, "provider": "GOOGLE", "model_name": "gemini-pro"},
        ]

        # Each ID should return its exact match
        result_1 = get_global_llm_config(-1)
        assert result_1["id"] == -1
        assert result_1["provider"] == "OPENAI"

        result_2 = get_global_llm_config(-2)
        assert result_2["id"] == -2
        assert result_2["provider"] == "ANTHROPIC"

        result_3 = get_global_llm_config(-3)
        assert result_3["id"] == -3
        assert result_3["provider"] == "GOOGLE"

    @patch("app.services.llm_service.config")
    def test_non_existent_negative_id_returns_none(self, mock_config):
        """Non-existent global config IDs must return None, not error."""
        mock_config.GLOBAL_LLM_CONFIGS = [
            {"id": -1, "provider": "OPENAI", "model_name": "gpt-4"},
        ]

        result = get_global_llm_config(-999)
        assert result is None


class TestSearchSpaceLLMInstanceRetrieval:
    """
    Tests for search space LLM instance retrieval.
    Validates correct role-to-field mapping and graceful error handling.
    """

    @pytest.mark.asyncio
    async def test_nonexistent_search_space_returns_none(self, mock_session):
        """
        Missing search space must return None, not raise exception.
        This prevents crashes when search spaces are deleted.
        """
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_search_space_llm_instance(
            mock_session, search_space_id=999, role=LLMRole.FAST
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_role_returns_none(self, mock_session):
        """
        Invalid role must return None to prevent undefined behavior.
        """
        mock_search_space = MagicMock()
        mock_search_space.fast_llm_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_search_space
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_search_space_llm_instance(
            mock_session, search_space_id=1, role="not_a_valid_role"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_unconfigured_llm_returns_none(self, mock_session):
        """
        When no LLM is configured for a role, return None.
        This is a valid state - not all search spaces have all LLMs.
        """
        mock_search_space = MagicMock()
        mock_search_space.fast_llm_id = None
        mock_search_space.long_context_llm_id = None
        mock_search_space.strategic_llm_id = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_search_space
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_search_space_llm_instance(
            mock_session, search_space_id=1, role=LLMRole.FAST
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.llm_service.get_global_llm_config")
    @patch("app.services.llm_service.ChatLiteLLM")
    async def test_global_config_creates_llm_instance(
        self, mock_chat_litellm, mock_get_global, mock_session
    ):
        """
        Global config (negative ID) should create an LLM instance.
        """
        mock_search_space = MagicMock()
        mock_search_space.fast_llm_id = -1  # Global config ID

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_search_space
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_get_global.return_value = {
            "id": -1,
            "provider": "OPENAI",
            "model_name": "gpt-4",
            "api_key": "test-key",
        }

        mock_llm_instance = MagicMock()
        mock_chat_litellm.return_value = mock_llm_instance

        result = await get_search_space_llm_instance(
            mock_session, search_space_id=1, role=LLMRole.FAST
        )

        # Must return an LLM instance
        assert result == mock_llm_instance
        # Must have attempted to create ChatLiteLLM
        mock_chat_litellm.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.llm_service.get_global_llm_config")
    async def test_missing_global_config_returns_none(
        self, mock_get_global, mock_session
    ):
        """
        If global config ID is set but config doesn't exist, return None.
        This handles config deletion gracefully.
        """
        mock_search_space = MagicMock()
        mock_search_space.fast_llm_id = -1  # Global ID that doesn't exist

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_search_space
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_get_global.return_value = None  # Config not found

        result = await get_search_space_llm_instance(
            mock_session, search_space_id=1, role=LLMRole.FAST
        )

        assert result is None


class TestRoleToLLMMapping:
    """
    Tests validating that convenience functions map to correct roles.
    Wrong mapping would use wrong model (e.g., slow model for fast tasks).
    """

    @pytest.mark.asyncio
    @patch("app.services.llm_service.get_search_space_llm_instance")
    async def test_get_fast_llm_uses_fast_role(self, mock_get_instance, mock_session):
        """get_fast_llm must request LLMRole.FAST specifically."""
        mock_llm = MagicMock()
        mock_get_instance.return_value = mock_llm

        await get_fast_llm(mock_session, search_space_id=1)

        mock_get_instance.assert_called_once_with(
            mock_session, 1, LLMRole.FAST
        )

    @pytest.mark.asyncio
    @patch("app.services.llm_service.get_search_space_llm_instance")
    async def test_get_long_context_llm_uses_long_context_role(
        self, mock_get_instance, mock_session
    ):
        """get_long_context_llm must request LLMRole.LONG_CONTEXT specifically."""
        mock_llm = MagicMock()
        mock_get_instance.return_value = mock_llm

        await get_long_context_llm(mock_session, search_space_id=1)

        mock_get_instance.assert_called_once_with(
            mock_session, 1, LLMRole.LONG_CONTEXT
        )

    @pytest.mark.asyncio
    @patch("app.services.llm_service.get_search_space_llm_instance")
    async def test_get_strategic_llm_uses_strategic_role(
        self, mock_get_instance, mock_session
    ):
        """get_strategic_llm must request LLMRole.STRATEGIC specifically."""
        mock_llm = MagicMock()
        mock_get_instance.return_value = mock_llm

        await get_strategic_llm(mock_session, search_space_id=1)

        mock_get_instance.assert_called_once_with(
            mock_session, 1, LLMRole.STRATEGIC
        )

    @pytest.mark.asyncio
    @patch("app.services.llm_service.get_search_space_llm_instance")
    async def test_convenience_functions_return_llm_instance(
        self, mock_get_instance, mock_session
    ):
        """Convenience functions must return the LLM instance unchanged."""
        mock_llm = MagicMock()
        mock_llm.model_name = "test-model"
        mock_get_instance.return_value = mock_llm

        fast = await get_fast_llm(mock_session, search_space_id=1)
        assert fast == mock_llm

        mock_get_instance.reset_mock()
        mock_get_instance.return_value = mock_llm

        long_context = await get_long_context_llm(mock_session, search_space_id=1)
        assert long_context == mock_llm

        mock_get_instance.reset_mock()
        mock_get_instance.return_value = mock_llm

        strategic = await get_strategic_llm(mock_session, search_space_id=1)
        assert strategic == mock_llm
