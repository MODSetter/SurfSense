"""
Extended tests for LLM service.
Tests LLM configuration validation and instance creation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_service import (
    LLMRole,
    get_global_llm_config,
    validate_llm_config,
    get_search_space_llm_instance,
    get_long_context_llm,
    get_fast_llm,
    get_strategic_llm,
)


class TestLLMRoleExtended:
    """Extended tests for LLMRole constants."""

    def test_role_long_context(self):
        """Test long context role value."""
        assert LLMRole.LONG_CONTEXT == "long_context"

    def test_role_fast(self):
        """Test fast role value."""
        assert LLMRole.FAST == "fast"

    def test_role_strategic(self):
        """Test strategic role value."""
        assert LLMRole.STRATEGIC == "strategic"


class TestGetGlobalLLMConfig:
    """Tests for get_global_llm_config function."""

    def test_returns_none_for_positive_id(self):
        """Test that positive IDs return None."""
        result = get_global_llm_config(1)
        assert result is None

    def test_returns_none_for_zero_id(self):
        """Test that zero ID returns None."""
        result = get_global_llm_config(0)
        assert result is None

    def test_returns_config_for_matching_negative_id(self):
        """Test that matching negative ID returns config."""
        with patch("app.services.llm_service.config") as mock_config:
            mock_config.GLOBAL_LLM_CONFIGS = [
                {"id": -1, "name": "GPT-4", "provider": "OPENAI"},
                {"id": -2, "name": "Claude", "provider": "ANTHROPIC"},
            ]
            
            result = get_global_llm_config(-1)
            
            assert result is not None
            assert result["name"] == "GPT-4"

    def test_returns_none_for_non_matching_negative_id(self):
        """Test that non-matching negative ID returns None."""
        with patch("app.services.llm_service.config") as mock_config:
            mock_config.GLOBAL_LLM_CONFIGS = [
                {"id": -1, "name": "GPT-4"},
            ]
            
            result = get_global_llm_config(-999)
            
            assert result is None


class TestValidateLLMConfig:
    """Tests for validate_llm_config function."""

    @pytest.mark.asyncio
    async def test_validate_llm_config_success(self):
        """Test successful LLM config validation."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            is_valid, error = await validate_llm_config(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="sk-test-key",
            )
            
            assert is_valid is True
            assert error == ""

    @pytest.mark.asyncio
    async def test_validate_llm_config_empty_response(self):
        """Test validation fails with empty response."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = ""
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            is_valid, error = await validate_llm_config(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="sk-test-key",
            )
            
            assert is_valid is False
            assert "empty response" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_llm_config_exception(self):
        """Test validation handles exceptions."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))
            MockChatLiteLLM.return_value = mock_llm
            
            is_valid, error = await validate_llm_config(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="sk-invalid-key",
            )
            
            assert is_valid is False
            assert "API Error" in error

    @pytest.mark.asyncio
    async def test_validate_llm_config_with_custom_provider(self):
        """Test validation with custom provider."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            is_valid, error = await validate_llm_config(
                provider="OPENAI",
                model_name="custom-model",
                api_key="sk-test-key",
                custom_provider="custom/provider",
            )
            
            assert is_valid is True
            # Verify custom provider was used in model string
            call_args = MockChatLiteLLM.call_args
            assert "custom/provider" in call_args.kwargs.get("model", "")

    @pytest.mark.asyncio
    async def test_validate_llm_config_with_api_base(self):
        """Test validation with custom API base."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            is_valid, error = await validate_llm_config(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="sk-test-key",
                api_base="https://custom.api.com",
            )
            
            assert is_valid is True
            call_args = MockChatLiteLLM.call_args
            assert call_args.kwargs.get("api_base") == "https://custom.api.com"


class TestGetSearchSpaceLLMInstance:
    """Tests for get_search_space_llm_instance function."""

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_search_space(self):
        """Test returns None when search space doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await get_search_space_llm_instance(
            session=mock_session,
            search_space_id=999,
            role=LLMRole.FAST,
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_role(self):
        """Test returns None for invalid role."""
        mock_session = AsyncMock()
        
        # Mock search space exists
        mock_search_space = MagicMock()
        mock_search_space.id = 1
        mock_search_space.fast_llm_id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_search_space
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await get_search_space_llm_instance(
            session=mock_session,
            search_space_id=1,
            role="invalid_role",
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_llm_configured(self):
        """Test returns None when LLM is not configured for role."""
        mock_session = AsyncMock()
        
        # Mock search space with no LLM configured
        mock_search_space = MagicMock()
        mock_search_space.id = 1
        mock_search_space.fast_llm_id = None
        mock_search_space.long_context_llm_id = None
        mock_search_space.strategic_llm_id = None
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_search_space
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        result = await get_search_space_llm_instance(
            session=mock_session,
            search_space_id=1,
            role=LLMRole.FAST,
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_instance_for_global_config(self):
        """Test returns LLM instance for global config."""
        mock_session = AsyncMock()
        
        # Mock search space with global config
        mock_search_space = MagicMock()
        mock_search_space.id = 1
        mock_search_space.fast_llm_id = -1  # Global config
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_search_space
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.services.llm_service.config") as mock_config:
            mock_config.GLOBAL_LLM_CONFIGS = [
                {
                    "id": -1,
                    "name": "GPT-4",
                    "provider": "OPENAI",
                    "model_name": "gpt-4",
                    "api_key": "sk-test",
                    "api_base": None,
                    "custom_provider": None,
                    "litellm_params": None,
                }
            ]
            
            with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
                mock_llm = MagicMock()
                MockChatLiteLLM.return_value = mock_llm
                
                result = await get_search_space_llm_instance(
                    session=mock_session,
                    search_space_id=1,
                    role=LLMRole.FAST,
                )
                
                assert result is not None
                assert MockChatLiteLLM.called


class TestConvenienceFunctions:
    """Tests for convenience wrapper functions."""

    @pytest.mark.asyncio
    async def test_get_long_context_llm(self):
        """Test get_long_context_llm uses correct role."""
        mock_session = AsyncMock()
        
        with patch("app.services.llm_service.get_search_space_llm_instance") as mock_get:
            mock_get.return_value = MagicMock()
            
            await get_long_context_llm(mock_session, 1)
            
            mock_get.assert_called_once_with(mock_session, 1, LLMRole.LONG_CONTEXT)

    @pytest.mark.asyncio
    async def test_get_fast_llm(self):
        """Test get_fast_llm uses correct role."""
        mock_session = AsyncMock()
        
        with patch("app.services.llm_service.get_search_space_llm_instance") as mock_get:
            mock_get.return_value = MagicMock()
            
            await get_fast_llm(mock_session, 1)
            
            mock_get.assert_called_once_with(mock_session, 1, LLMRole.FAST)

    @pytest.mark.asyncio
    async def test_get_strategic_llm(self):
        """Test get_strategic_llm uses correct role."""
        mock_session = AsyncMock()
        
        with patch("app.services.llm_service.get_search_space_llm_instance") as mock_get:
            mock_get.return_value = MagicMock()
            
            await get_strategic_llm(mock_session, 1)
            
            mock_get.assert_called_once_with(mock_session, 1, LLMRole.STRATEGIC)


class TestProviderMapping:
    """Tests for provider string mapping."""

    @pytest.mark.asyncio
    async def test_openai_provider_mapping(self):
        """Test OPENAI maps to openai."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            await validate_llm_config(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="sk-test",
            )
            
            call_args = MockChatLiteLLM.call_args
            assert "openai/gpt-4" in call_args.kwargs.get("model", "")

    @pytest.mark.asyncio
    async def test_anthropic_provider_mapping(self):
        """Test ANTHROPIC maps to anthropic."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            await validate_llm_config(
                provider="ANTHROPIC",
                model_name="claude-3",
                api_key="sk-test",
            )
            
            call_args = MockChatLiteLLM.call_args
            assert "anthropic/claude-3" in call_args.kwargs.get("model", "")

    @pytest.mark.asyncio
    async def test_google_provider_mapping(self):
        """Test GOOGLE maps to gemini."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            await validate_llm_config(
                provider="GOOGLE",
                model_name="gemini-pro",
                api_key="test-key",
            )
            
            call_args = MockChatLiteLLM.call_args
            assert "gemini/gemini-pro" in call_args.kwargs.get("model", "")

    @pytest.mark.asyncio
    async def test_ollama_provider_mapping(self):
        """Test OLLAMA maps to ollama."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            await validate_llm_config(
                provider="OLLAMA",
                model_name="llama2",
                api_key="",
                api_base="http://localhost:11434",
            )
            
            call_args = MockChatLiteLLM.call_args
            assert "ollama/llama2" in call_args.kwargs.get("model", "")


class TestLiteLLMParams:
    """Tests for litellm_params handling."""

    @pytest.mark.asyncio
    async def test_litellm_params_passed_to_instance(self):
        """Test that litellm_params are passed to ChatLiteLLM."""
        with patch("app.services.llm_service.ChatLiteLLM") as MockChatLiteLLM:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Hello!"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockChatLiteLLM.return_value = mock_llm
            
            await validate_llm_config(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="sk-test",
                litellm_params={"temperature": 0.7, "max_tokens": 1000},
            )
            
            call_args = MockChatLiteLLM.call_args
            assert call_args.kwargs.get("temperature") == 0.7
            assert call_args.kwargs.get("max_tokens") == 1000
