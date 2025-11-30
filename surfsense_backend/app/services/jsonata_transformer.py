"""
JSONata transformation service for standardizing connector responses.

This service provides a declarative transformation layer between external API
responses and SurfSense's internal data models. Instead of writing custom Python
code for each connector, transformations are defined using JSONata expressions.

Usage:
    from app.services.jsonata_transformer import transformer

    # Transform using registered template
    result = transformer.transform("github", github_api_response)

    # Transform using custom expression
    result = transformer.transform_custom(
        '{ "title": title, "content": body }',
        raw_data
    )
"""

from typing import Any

import jsonata
from jsonata import JsonataError


class JSONataTransformer:
    """Service for applying JSONata transformations to connector data."""

    def __init__(self):
        """Initialize the transformer with an empty template registry."""
        # Store compiled expressions instead of raw strings for performance
        self.templates: dict[str, Any] = {}

    def register_template(self, connector_type: str, jsonata_expression: str) -> None:
        """
        Register and pre-compile a JSONata transformation template for a connector.

        Templates are compiled once during registration to eliminate redundant
        compilation overhead on every transform() call.

        Args:
            connector_type: Identifier for the connector (e.g., 'github', 'gmail')
            jsonata_expression: JSONata expression to transform the data

        Raises:
            ValueError: If the JSONata expression is invalid

        Example:
            >>> transformer.register_template(
            ...     "github",
            ...     '{ "title": title, "content": body }'
            ... )
        """
        try:
            # Pre-compile the expression for performance
            compiled_expression = jsonata.Jsonata(jsonata_expression)
            self.templates[connector_type] = compiled_expression
        except JsonataError as e:
            raise ValueError(
                f"Invalid JSONata expression for connector '{connector_type}': {str(e)}"
            ) from e

    def transform(
        self, connector_type: str, data: dict[str, Any]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Transform connector response using pre-compiled template.

        Args:
            connector_type: The connector type to use for transformation
            data: Raw data from the connector API

        Returns:
            Transformed data according to the template

        Raises:
            ValueError: If JSONata transformation fails

        Example:
            >>> result = transformer.transform("github", {
            ...     "title": "Bug report",
            ...     "body": "Description..."
            ... })
        """
        if connector_type not in self.templates:
            # Fallback: return original data if no template registered
            return data

        # Use pre-compiled expression (no compilation overhead)
        compiled_expression = self.templates[connector_type]
        try:
            return compiled_expression.evaluate(data)
        except JsonataError as e:
            raise ValueError(
                f"JSONata transformation failed for connector '{connector_type}': {str(e)}"
            ) from e

    def transform_custom(
        self, jsonata_expression: str, data: dict[str, Any]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Transform data using a custom JSONata expression.

        This method is useful for testing transformations or one-off transformations
        that don't need to be registered as templates.

        Args:
            jsonata_expression: JSONata expression to apply
            data: Raw data to transform

        Returns:
            Transformed data

        Raises:
            ValueError: If JSONata expression is invalid or transformation fails

        Example:
            >>> result = transformer.transform_custom(
            ...     '{ "name": user.name, "email": user.email }',
            ...     {"user": {"name": "John", "email": "john@example.com"}}
            ... )
        """
        try:
            expression = jsonata.Jsonata(jsonata_expression)
            return expression.evaluate(data)
        except JsonataError as e:
            raise ValueError(
                f"Invalid JSONata expression or transformation failed: {str(e)}"
            ) from e

    def has_template(self, connector_type: str) -> bool:
        """
        Check if a template is registered for a connector type.

        Args:
            connector_type: The connector type to check

        Returns:
            True if a template is registered, False otherwise
        """
        return connector_type in self.templates

    def list_templates(self) -> list[str]:
        """
        List all registered template names.

        Returns:
            List of connector types with registered templates
        """
        return list(self.templates.keys())


# Global transformer instance
# This singleton is initialized on application startup and templates are registered
# from the jsonata_templates configuration module
transformer = JSONataTransformer()
