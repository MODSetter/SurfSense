"""
Tests for LLM config routes.
Tests API endpoints with mocked database sessions and authentication.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.routes.llm_config_routes import (
    get_global_llm_configs,
    create_llm_config,
    read_llm_configs,
    read_llm_config,
    update_llm_config,
    delete_llm_config,
    get_llm_preferences,
    update_llm_preferences,
    LLMPreferencesUpdate,
)
from app.schemas import LLMConfigCreate, LLMConfigUpdate
from app.db import LiteLLMProvider


class TestGetGlobalLLMConfigs:
    """Tests for the get_global_llm_configs endpoint."""

    @pytest.mark.asyncio
    async def test_returns_global_configs_without_api_keys(self):
        """Test that global configs are returned without exposing API keys."""
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        with patch("app.routes.llm_config_routes.config") as mock_config:
            mock_config.GLOBAL_LLM_CONFIGS = [
                {
                    "id": -1,
                    "name": "GPT-4",
                    "provider": "OPENAI",
                    "custom_provider": None,
                    "model_name": "gpt-4",
                    "api_key": "sk-secret-key",
                    "api_base": None,
                    "language": "en",
                    "litellm_params": {},
                },
            ]
            
            result = await get_global_llm_configs(user=mock_user)
            
            assert len(result) == 1
            # API key should not be in the response
            assert "api_key" not in result[0] or result[0].get("api_key") != "sk-secret-key"
            assert result[0]["name"] == "GPT-4"
            assert result[0]["is_global"] is True

    @pytest.mark.asyncio
    async def test_handles_empty_global_configs(self):
        """Test handling when no global configs are configured."""
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        with patch("app.routes.llm_config_routes.config") as mock_config:
            mock_config.GLOBAL_LLM_CONFIGS = []
            
            result = await get_global_llm_configs(user=mock_user)
            
            assert result == []


class TestCreateLLMConfig:
    """Tests for the create_llm_config endpoint."""

    @pytest.mark.asyncio
    async def test_create_llm_config_invalid_validation(self):
        """Test creating LLM config with invalid validation."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        llm_config_data = LLMConfigCreate(
            name="Test LLM",
            provider=LiteLLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="invalid-key",
            search_space_id=1,
        )
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with patch("app.routes.llm_config_routes.validate_llm_config") as mock_validate:
                mock_validate.return_value = (False, "Invalid API key")
                
                with pytest.raises(HTTPException) as exc_info:
                    await create_llm_config(
                        llm_config=llm_config_data,
                        session=mock_session,
                        user=mock_user,
                    )
                
                assert exc_info.value.status_code == 400
                assert "Invalid LLM configuration" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_llm_config_success(self):
        """Test successful LLM config creation."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        llm_config_data = LLMConfigCreate(
            name="Test LLM",
            provider=LiteLLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="sk-valid-key",
            search_space_id=1,
        )
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with patch("app.routes.llm_config_routes.validate_llm_config") as mock_validate:
                mock_validate.return_value = (True, "")
                
                with patch("app.routes.llm_config_routes.LLMConfig") as MockLLMConfig:
                    mock_config = MagicMock()
                    mock_config.id = 1
                    mock_config.name = "Test LLM"
                    MockLLMConfig.return_value = mock_config
                    
                    result = await create_llm_config(
                        llm_config=llm_config_data,
                        session=mock_session,
                        user=mock_user,
                    )
                    
                    assert mock_session.add.called
                    assert mock_session.commit.called


class TestReadLLMConfigs:
    """Tests for the read_llm_configs endpoint."""

    @pytest.mark.asyncio
    async def test_read_llm_configs_success(self):
        """Test successful reading of LLM configs."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await read_llm_configs(
                search_space_id=1,
                skip=0,
                limit=200,
                session=mock_session,
                user=mock_user,
            )
            
            assert isinstance(result, list)


class TestReadLLMConfig:
    """Tests for the read_llm_config endpoint."""

    @pytest.mark.asyncio
    async def test_read_llm_config_not_found(self):
        """Test reading non-existent LLM config."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with pytest.raises(HTTPException) as exc_info:
            await read_llm_config(
                llm_config_id=999,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_read_llm_config_success(self):
        """Test successful reading of LLM config."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock existing config
        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.search_space_id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_config
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await read_llm_config(
                llm_config_id=1,
                session=mock_session,
                user=mock_user,
            )
            
            assert result.id == 1


class TestUpdateLLMConfig:
    """Tests for the update_llm_config endpoint."""

    @pytest.mark.asyncio
    async def test_update_llm_config_not_found(self):
        """Test updating non-existent LLM config."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        update_data = LLMConfigUpdate(name="Updated Name")
        
        with pytest.raises(HTTPException) as exc_info:
            await update_llm_config(
                llm_config_id=999,
                llm_config_update=update_data,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 404


class TestDeleteLLMConfig:
    """Tests for the delete_llm_config endpoint."""

    @pytest.mark.asyncio
    async def test_delete_llm_config_not_found(self):
        """Test deleting non-existent LLM config."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_llm_config(
                llm_config_id=999,
                session=mock_session,
                user=mock_user,
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_llm_config_success(self):
        """Test successful LLM config deletion."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock existing config
        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.search_space_id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_config
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            result = await delete_llm_config(
                llm_config_id=1,
                session=mock_session,
                user=mock_user,
            )
            
            assert result["message"] == "LLM configuration deleted successfully"
            assert mock_session.delete.called
            assert mock_session.commit.called


class TestGetLLMPreferences:
    """Tests for the get_llm_preferences endpoint."""

    @pytest.mark.asyncio
    async def test_get_llm_preferences_not_found(self):
        """Test getting preferences for non-existent search space."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_llm_preferences(
                    search_space_id=999,
                    session=mock_session,
                    user=mock_user,
                )
            
            assert exc_info.value.status_code == 404


class TestUpdateLLMPreferences:
    """Tests for the update_llm_preferences endpoint."""

    @pytest.mark.asyncio
    async def test_update_llm_preferences_search_space_not_found(self):
        """Test updating preferences for non-existent search space."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        preferences = LLMPreferencesUpdate(fast_llm_id=1)
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await update_llm_preferences(
                    search_space_id=999,
                    preferences=preferences,
                    session=mock_session,
                    user=mock_user,
                )
            
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_llm_preferences_global_config_not_found(self):
        """Test updating with non-existent global config."""
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        
        # Mock search space exists
        mock_search_space = MagicMock()
        mock_search_space.id = 1
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_search_space
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.rollback = AsyncMock()
        
        preferences = LLMPreferencesUpdate(fast_llm_id=-999)  # Non-existent global config
        
        with patch("app.routes.llm_config_routes.check_permission") as mock_check:
            mock_check.return_value = None
            
            with patch("app.routes.llm_config_routes.config") as mock_config:
                mock_config.GLOBAL_LLM_CONFIGS = []
                
                with pytest.raises(HTTPException) as exc_info:
                    await update_llm_preferences(
                        search_space_id=1,
                        preferences=preferences,
                        session=mock_session,
                        user=mock_user,
                    )
                
                assert exc_info.value.status_code == 404
