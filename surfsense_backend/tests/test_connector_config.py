"""
Tests for the connector configuration validation in validators module.
"""

import pytest
from fastapi import HTTPException

from app.utils.validators import validate_connector_config


class TestValidateConnectorConfig:
    """Tests for validate_connector_config function."""

    def test_invalid_config_type_raises_error(self):
        """Test that non-dict config raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config("TAVILY_API", "not a dict")
        assert "must be a dictionary" in str(exc_info.value)

    def test_boolean_config_raises_error(self):
        """Test that boolean config raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config("TAVILY_API", True)
        assert "must be a dictionary" in str(exc_info.value)

    def test_tavily_api_valid_config(self):
        """Test valid Tavily API configuration."""
        config = {"TAVILY_API_KEY": "test-api-key-123"}
        result = validate_connector_config("TAVILY_API", config)
        assert result == config

    def test_tavily_api_missing_key_raises_error(self):
        """Test that missing TAVILY_API_KEY raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config("TAVILY_API", {})
        assert "TAVILY_API_KEY" in str(exc_info.value)

    def test_tavily_api_empty_key_raises_error(self):
        """Test that empty TAVILY_API_KEY raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config("TAVILY_API", {"TAVILY_API_KEY": ""})
        assert "cannot be empty" in str(exc_info.value)

    def test_tavily_api_unexpected_key_raises_error(self):
        """Test that unexpected key in config raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config(
                "TAVILY_API",
                {"TAVILY_API_KEY": "test-key", "UNEXPECTED_KEY": "value"},
            )
        assert "may only contain" in str(exc_info.value)

    def test_linkup_api_valid_config(self):
        """Test valid LinkUp API configuration."""
        config = {"LINKUP_API_KEY": "linkup-key-123"}
        result = validate_connector_config("LINKUP_API", config)
        assert result == config

    def test_searxng_api_valid_config(self):
        """Test valid SearxNG API configuration."""
        config = {"SEARXNG_HOST": "https://searxng.example.com"}
        result = validate_connector_config("SEARXNG_API", config)
        assert result == config

    def test_searxng_api_with_optional_params(self):
        """Test SearxNG API with optional parameters."""
        config = {
            "SEARXNG_HOST": "https://searxng.example.com",
            "SEARXNG_API_KEY": "optional-key",
            "SEARXNG_ENGINES": "google,bing",
            "SEARXNG_LANGUAGE": "en",
        }
        result = validate_connector_config("SEARXNG_API", config)
        assert result == config

    def test_searxng_api_invalid_host_raises_error(self):
        """Test that invalid SEARXNG_HOST raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config("SEARXNG_API", {"SEARXNG_HOST": "not-a-url"})
        assert "Invalid base URL" in str(exc_info.value)

    def test_slack_connector_valid_config(self):
        """Test valid Slack connector configuration."""
        config = {"SLACK_BOT_TOKEN": "xoxb-token-123"}
        result = validate_connector_config("SLACK_CONNECTOR", config)
        assert result == config

    def test_notion_connector_valid_config(self):
        """Test valid Notion connector configuration."""
        config = {"NOTION_INTEGRATION_TOKEN": "secret_token_123"}
        result = validate_connector_config("NOTION_CONNECTOR", config)
        assert result == config

    def test_github_connector_valid_config(self):
        """Test valid GitHub connector configuration."""
        config = {
            "GITHUB_PAT": "ghp_token_123",
            "repo_full_names": ["owner/repo1", "owner/repo2"],
        }
        result = validate_connector_config("GITHUB_CONNECTOR", config)
        assert result == config

    def test_github_connector_empty_repos_raises_error(self):
        """Test that empty repo_full_names raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config(
                "GITHUB_CONNECTOR",
                {"GITHUB_PAT": "ghp_token_123", "repo_full_names": []},
            )
        assert "non-empty list" in str(exc_info.value)

    def test_jira_connector_valid_config(self):
        """Test valid Jira connector configuration."""
        config = {
            "JIRA_EMAIL": "user@example.com",
            "JIRA_API_TOKEN": "api-token-123",
            "JIRA_BASE_URL": "https://company.atlassian.net",
        }
        result = validate_connector_config("JIRA_CONNECTOR", config)
        assert result == config

    def test_jira_connector_invalid_email_raises_error(self):
        """Test that invalid JIRA_EMAIL raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config(
                "JIRA_CONNECTOR",
                {
                    "JIRA_EMAIL": "not-an-email",
                    "JIRA_API_TOKEN": "token",
                    "JIRA_BASE_URL": "https://company.atlassian.net",
                },
            )
        assert "Invalid email" in str(exc_info.value)

    def test_jira_connector_invalid_url_raises_error(self):
        """Test that invalid JIRA_BASE_URL raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config(
                "JIRA_CONNECTOR",
                {
                    "JIRA_EMAIL": "user@example.com",
                    "JIRA_API_TOKEN": "token",
                    "JIRA_BASE_URL": "not-a-url",
                },
            )
        assert "Invalid base URL" in str(exc_info.value)

    def test_confluence_connector_valid_config(self):
        """Test valid Confluence connector configuration."""
        config = {
            "CONFLUENCE_BASE_URL": "https://company.atlassian.net/wiki",
            "CONFLUENCE_EMAIL": "user@example.com",
            "CONFLUENCE_API_TOKEN": "api-token-123",
        }
        result = validate_connector_config("CONFLUENCE_CONNECTOR", config)
        assert result == config

    def test_linear_connector_valid_config(self):
        """Test valid Linear connector configuration."""
        config = {"LINEAR_API_KEY": "lin_api_key_123"}
        result = validate_connector_config("LINEAR_CONNECTOR", config)
        assert result == config

    def test_discord_connector_valid_config(self):
        """Test valid Discord connector configuration."""
        config = {"DISCORD_BOT_TOKEN": "discord-token-123"}
        result = validate_connector_config("DISCORD_CONNECTOR", config)
        assert result == config

    def test_clickup_connector_valid_config(self):
        """Test valid ClickUp connector configuration."""
        config = {"CLICKUP_API_TOKEN": "pk_token_123"}
        result = validate_connector_config("CLICKUP_CONNECTOR", config)
        assert result == config

    def test_luma_connector_valid_config(self):
        """Test valid Luma connector configuration."""
        config = {"LUMA_API_KEY": "luma-key-123"}
        result = validate_connector_config("LUMA_CONNECTOR", config)
        assert result == config

    def test_webcrawler_connector_valid_without_api_key(self):
        """Test valid WebCrawler connector without API key (optional)."""
        config = {}
        result = validate_connector_config("WEBCRAWLER_CONNECTOR", config)
        assert result == config

    def test_webcrawler_connector_valid_with_api_key(self):
        """Test valid WebCrawler connector with API key."""
        config = {"FIRECRAWL_API_KEY": "fc-api-key-123"}
        result = validate_connector_config("WEBCRAWLER_CONNECTOR", config)
        assert result == config

    def test_webcrawler_connector_invalid_api_key_format(self):
        """Test that invalid Firecrawl API key format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config(
                "WEBCRAWLER_CONNECTOR",
                {"FIRECRAWL_API_KEY": "invalid-format-key"},
            )
        assert "should start with 'fc-'" in str(exc_info.value)

    def test_webcrawler_connector_valid_with_urls(self):
        """Test valid WebCrawler connector with initial URLs."""
        config = {"INITIAL_URLS": "https://example.com\nhttps://another.com"}
        result = validate_connector_config("WEBCRAWLER_CONNECTOR", config)
        assert result == config

    def test_webcrawler_connector_invalid_urls(self):
        """Test that invalid URL in INITIAL_URLS raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_connector_config(
                "WEBCRAWLER_CONNECTOR",
                {"INITIAL_URLS": "https://valid.com\nnot-a-valid-url"},
            )
        assert "Invalid URL format" in str(exc_info.value)

    def test_baidu_search_api_valid_config(self):
        """Test valid Baidu Search API configuration."""
        config = {"BAIDU_API_KEY": "baidu-api-key-123"}
        result = validate_connector_config("BAIDU_SEARCH_API", config)
        assert result == config

    def test_baidu_search_api_with_optional_params(self):
        """Test Baidu Search API with optional parameters."""
        config = {
            "BAIDU_API_KEY": "baidu-api-key-123",
            "BAIDU_MODEL": "ernie-4.0",
            "BAIDU_SEARCH_SOURCE": "baidu_search_v2",
            "BAIDU_ENABLE_DEEP_SEARCH": True,
        }
        result = validate_connector_config("BAIDU_SEARCH_API", config)
        assert result == config

    def test_serper_api_valid_config(self):
        """Test valid Serper API configuration."""
        config = {"SERPER_API_KEY": "serper-api-key-123"}
        result = validate_connector_config("SERPER_API", config)
        assert result == config

    def test_unknown_connector_type_passes_through(self):
        """Test that unknown connector type passes config through unchanged."""
        config = {"ANY_KEY": "any_value"}
        result = validate_connector_config("UNKNOWN_CONNECTOR", config)
        assert result == config

    def test_connector_type_enum_handling(self):
        """Test that connector type enum is handled correctly."""
        from unittest.mock import MagicMock

        mock_enum = MagicMock()
        mock_enum.value = "TAVILY_API"

        config = {"TAVILY_API_KEY": "test-key"}
        # The function should handle enum-like objects
        result = validate_connector_config(mock_enum, config)
        assert result == config
