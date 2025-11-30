"""
Unit tests for JSONata transformation service.

Tests cover:
- Basic transformation functionality
- Template registration and retrieval
- Error handling
- Connector-specific transformations
"""

import pytest

from app.services.jsonata_transformer import JSONataTransformer


@pytest.fixture
def transformer():
    """Fixture that provides a fresh JSONataTransformer instance for each test."""
    return JSONataTransformer()


class TestJSONataTransformer:
    """Test suite for JSONataTransformer class."""

    def test_transformer_initialization(self, transformer):
        """Test that transformer initializes with empty template registry."""
        assert transformer.templates == {}
        assert transformer.list_templates() == []

    def test_register_template(self, transformer):
        """Test registering a transformation template."""
        template = '{ "title": title, "content": body }'

        transformer.register_template("test_connector", template)

        # Verify template is registered
        assert "test_connector" in transformer.templates
        assert transformer.has_template("test_connector") is True
        # Templates are now stored as compiled expressions, not raw strings
        assert transformer.templates["test_connector"] is not None
        # Verify the compiled template can be used for transformation
        result = transformer.transform("test_connector", {"title": "Test", "body": "Content"})
        assert result["title"] == "Test"
        assert result["content"] == "Content"

    def test_transform_with_registered_template(self, transformer):
        """Test transformation using a registered template."""
        template = '{ "title": title, "content": body }'
        transformer.register_template("github", template)

        github_response = {
            "title": "Bug in login",
            "body": "Login fails when...",
            "extra_field": "ignored",
        }

        result = transformer.transform("github", github_response)

        assert result["title"] == "Bug in login"
        assert result["content"] == "Login fails when..."
        assert "extra_field" not in result

    def test_transform_without_registered_template(self, transformer):
        """Test that transform returns original data when no template exists."""
        original_data = {"title": "Test", "body": "Content"}

        result = transformer.transform("unknown_connector", original_data)

        assert result == original_data

    def test_transform_custom(self, transformer):
        """Test transformation with custom JSONata expression."""
        data = {
            "user": {"name": "John Doe", "email": "john@example.com"},
            "timestamp": "2025-11-29T10:00:00Z",
        }

        expression = '{ "name": user.name, "email": user.email }'
        result = transformer.transform_custom(expression, data)

        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert "timestamp" not in result

    def test_github_issue_transformation(self, transformer):
        """Test GitHub issue transformation with realistic data."""
        template = """
        {
            "title": title,
            "content": body,
            "document_type": "GITHUB_CONNECTOR",
            "document_metadata": {
                "url": html_url,
                "author": user.login,
                "state": state
            }
        }
        """
        transformer.register_template("github", template)

        github_response = {
            "title": "Bug in authentication",
            "body": "Users cannot log in",
            "html_url": "https://github.com/org/repo/issues/123",
            "user": {"login": "testuser", "id": 12345},
            "state": "open",
            "created_at": "2025-11-29T10:00:00Z",
        }

        result = transformer.transform("github", github_response)

        assert result["title"] == "Bug in authentication"
        assert result["content"] == "Users cannot log in"
        assert result["document_type"] == "GITHUB_CONNECTOR"
        assert result["document_metadata"]["url"] == "https://github.com/org/repo/issues/123"
        assert result["document_metadata"]["author"] == "testuser"
        assert result["document_metadata"]["state"] == "open"

    def test_slack_message_transformation(self, transformer):
        """Test Slack message transformation with metadata extraction."""
        template = """
        {
            "title": $substring(text, 0, 50),
            "content": text,
            "document_type": "SLACK_CONNECTOR",
            "document_metadata": {
                "channel": channel,
                "user": user,
                "timestamp": ts
            }
        }
        """
        transformer.register_template("slack", template)

        slack_response = {
            "text": "This is a test message from Slack channel",
            "channel": "C12345",
            "user": "U67890",
            "ts": "1732876800.000000",
        }

        result = transformer.transform("slack", slack_response)

        assert result["title"] == "This is a test message from Slack channel"
        assert result["content"] == "This is a test message from Slack channel"
        assert result["document_type"] == "SLACK_CONNECTOR"
        assert result["document_metadata"]["channel"] == "C12345"

    def test_jsonata_array_transformation(self, transformer):
        """Test JSONata transformation that returns an array."""
        data = {
            "issues": [
                {"title": "Issue 1", "state": "open"},
                {"title": "Issue 2", "state": "closed"},
            ]
        }

        expression = "issues[state='open']"
        result = transformer.transform_custom(expression, data)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Issue 1"

    def test_jsonata_aggregation(self, transformer):
        """Test JSONata with aggregation functions."""
        data = {
            "items": [
                {"name": "Item 1", "price": 10},
                {"name": "Item 2", "price": 20},
                {"name": "Item 3", "price": 30},
            ]
        }

        expression = '{ "total": $sum(items.price), "count": $count(items) }'
        result = transformer.transform_custom(expression, data)

        assert result["total"] == 60
        assert result["count"] == 3

    def test_list_templates(self, transformer):
        """Test listing all registered templates."""
        transformer.register_template("github", "{ }")
        transformer.register_template("slack", "{ }")
        transformer.register_template("jira", "{ }")

        templates = transformer.list_templates()

        assert len(templates) == 3
        assert "github" in templates
        assert "slack" in templates
        assert "jira" in templates

    def test_has_template(self, transformer):
        """Test checking if template exists."""
        transformer.register_template("github", "{ }")

        assert transformer.has_template("github") is True
        assert transformer.has_template("slack") is False

    def test_invalid_jsonata_expression(self, transformer):
        """Test that invalid JSONata expression raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            transformer.transform_custom("{ invalid syntax }", {"data": "test"})

        assert "Invalid JSONata expression or transformation failed" in str(exc_info.value)

    def test_nested_data_extraction(self, transformer):
        """Test extracting deeply nested data."""
        data = {
            "response": {
                "data": {
                    "user": {
                        "profile": {
                            "name": "John Doe",
                            "contact": {"email": "john@example.com"},
                        }
                    }
                }
            }
        }

        expression = '{ "name": response.data.user.profile.name, "email": response.data.user.profile.contact.email }'
        result = transformer.transform_custom(expression, data)

        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"

    def test_malformed_input_empty_dict(self, transformer):
        """Test transformation handles empty dictionary gracefully."""
        template = """
        {
            "title": $exists(title) ? title : "Untitled",
            "content": $exists(body) ? body : "",
            "document_type": "TEST_CONNECTOR"
        }
        """
        transformer.register_template("test", template)

        result = transformer.transform("test", {})

        assert result["title"] == "Untitled"
        assert result["content"] == ""
        assert result["document_type"] == "TEST_CONNECTOR"

    def test_malformed_input_missing_nested_fields(self, transformer):
        """Test transformation handles missing nested fields without crashing."""
        template = """
        {
            "title": title,
            "author": $exists(user.name) ? user.name : "Unknown",
            "email": $exists(user.contact.email) ? user.contact.email : null
        }
        """
        transformer.register_template("test", template)

        # Data with partial structure - user exists but no nested contact
        incomplete_data = {"title": "Test Document", "user": {"name": "John"}}

        result = transformer.transform("test", incomplete_data)

        assert result["title"] == "Test Document"
        assert result["author"] == "John"
        assert result["email"] is None

    def test_malformed_input_null_values(self, transformer):
        """Test transformation handles explicit null values correctly."""
        template = """
        {
            "title": $exists(title) ? title : "Untitled",
            "assignee": $exists(assignee) ? assignee : null,
            "status": $exists(status) ? status : "unknown"
        }
        """
        transformer.register_template("test", template)

        data = {"title": "Task", "assignee": None, "status": None}

        result = transformer.transform("test", data)

        assert result["title"] == "Task"
        # $exists() returns false for null values
        assert result["assignee"] is None
        assert result["status"] == "unknown"

    def test_malformed_input_array_instead_of_object(self, transformer):
        """Test transformation handles unexpected array input."""
        template = '{ "items": $count($) }'
        transformer.register_template("test", template)

        # Passing array instead of object
        array_data = [{"id": 1}, {"id": 2}, {"id": 3}]

        result = transformer.transform("test", array_data)

        assert result["items"] == 3

    def test_malformed_input_string_instead_of_array(self, transformer):
        """Test transformation handles string where array expected."""
        template = """
        {
            "tags": $type(labels) = "array" ? labels : [labels]
        }
        """
        transformer.register_template("test", template)

        # String instead of array for labels
        data = {"labels": "bug"}

        result = transformer.transform("test", data)

        # Should wrap string in array
        assert result["tags"] == ["bug"]

    def test_invalid_template_registration(self, transformer):
        """Test that registering invalid template raises ValueError."""
        # Invalid JSONata syntax - unclosed brace
        invalid_template = '{ "title": title'

        with pytest.raises(ValueError) as exc_info:
            transformer.register_template("invalid", invalid_template)

        assert "Invalid JSONata expression" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    def test_transform_evaluation_error(self, transformer):
        """Test that transform raises ValueError when evaluation fails."""
        # Register a valid template that will fail during evaluation
        # Using $number() with non-numeric string causes evaluation error
        template = '{ "result": $number(value) }'
        transformer.register_template("test_connector", template)

        # Data that will cause evaluation to fail
        invalid_data = {"value": "not-a-number"}

        with pytest.raises(ValueError) as exc_info:
            transformer.transform("test_connector", invalid_data)

        # Verify the error message includes the connector type
        assert "JSONata transformation failed for connector 'test_connector'" in str(exc_info.value)

    def test_transformation_with_unicode_characters(self, transformer):
        """Test transformation handles unicode characters correctly."""
        template = '{ "title": title, "content": content }'
        transformer.register_template("test", template)

        data = {
            "title": "Unicode Test: 你好世界 🌍",
            "content": "Emoji support: ✅ 🚀 🎉",
        }

        result = transformer.transform("test", data)

        assert result["title"] == "Unicode Test: 你好世界 🌍"
        assert result["content"] == "Emoji support: ✅ 🚀 🎉"

    def test_transformation_with_very_large_array(self, transformer):
        """Test transformation performance with large arrays."""
        template = '{ "total": $sum(items.value), "count": $count(items) }'
        transformer.register_template("test", template)

        # Create large array
        large_array = [{"value": i} for i in range(1000)]
        data = {"items": large_array}

        result = transformer.transform("test", data)

        assert result["count"] == 1000
        assert result["total"] == sum(range(1000))
