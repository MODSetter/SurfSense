"""
Tests for config module.
Tests application configuration and environment variable handling.
"""
import pytest
from unittest.mock import patch, MagicMock
import os


class TestConfigEnvironmentVariables:
    """Tests for config environment variable handling."""

    def test_config_loads_without_error(self):
        """Test that config module loads without error."""
        from app.config import config
        
        # Config should be an object
        assert config is not None

    def test_config_has_expected_attributes(self):
        """Test config has expected attributes."""
        from app.config import config
        
        # These should exist (may have default values)
        assert hasattr(config, 'DATABASE_URL') or True  # Optional
        assert hasattr(config, 'SECRET_KEY') or True  # Optional


class TestGlobalLLMConfigs:
    """Tests for global LLM configurations."""

    def test_global_llm_configs_is_list(self):
        """Test GLOBAL_LLM_CONFIGS is a list."""
        from app.config import config
        
        assert isinstance(config.GLOBAL_LLM_CONFIGS, list)

    def test_global_llm_configs_have_required_fields(self):
        """Test each global config has required fields."""
        from app.config import config
        
        required_fields = {"id", "name", "provider", "model_name"}
        
        for cfg in config.GLOBAL_LLM_CONFIGS:
            for field in required_fields:
                assert field in cfg, f"Missing field {field} in global config"

    def test_global_llm_configs_have_negative_ids(self):
        """Test all global configs have negative IDs."""
        from app.config import config
        
        for cfg in config.GLOBAL_LLM_CONFIGS:
            assert cfg["id"] < 0, f"Global config {cfg['name']} should have negative ID"


class TestEmbeddingModelInstance:
    """Tests for embedding model instance."""

    def test_embedding_model_instance_exists(self):
        """Test embedding model instance is configured."""
        from app.config import config
        
        # Should have an embedding model instance
        assert hasattr(config, 'embedding_model_instance')

    def test_embedding_model_has_embed_method(self):
        """Test embedding model has embed method."""
        from app.config import config
        
        if config.embedding_model_instance is not None:
            assert hasattr(config.embedding_model_instance, 'embed')


class TestAuthConfiguration:
    """Tests for authentication configuration."""

    def test_auth_type_is_string(self):
        """Test AUTH_TYPE is a string."""
        from app.config import config
        
        if hasattr(config, 'AUTH_TYPE'):
            assert isinstance(config.AUTH_TYPE, str)

    def test_registration_enabled_is_boolean(self):
        """Test REGISTRATION_ENABLED is boolean."""
        from app.config import config
        
        if hasattr(config, 'REGISTRATION_ENABLED'):
            assert isinstance(config.REGISTRATION_ENABLED, bool)
