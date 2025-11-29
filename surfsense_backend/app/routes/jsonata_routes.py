"""
API endpoints for JSONata transformation management and testing.

These endpoints allow testing JSONata transformations interactively and
inspecting registered transformation templates.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.jsonata_transformer import transformer
from app.users import User, current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jsonata", tags=["jsonata"])


class TransformRequest(BaseModel):
    """Request model for testing custom JSONata transformations."""

    jsonata_expression: str = Field(
        ...,
        description="JSONata expression to apply to the data",
        examples=['{ "title": title, "content": body }'],
    )
    data: dict[str, Any] = Field(
        ...,
        description="Raw data to transform",
        examples=[{"title": "Test", "body": "Content"}],
    )


class TransformResponse(BaseModel):
    """Response model for transformation results."""

    result: dict[str, Any] | list[dict[str, Any]] = Field(
        ..., description="Transformed data"
    )


class TemplateInfo(BaseModel):
    """Information about a registered transformation template."""

    connector_type: str = Field(..., description="Connector identifier")
    has_template: bool = Field(..., description="Whether a template is registered")


class TemplatesListResponse(BaseModel):
    """Response model for listing all registered templates."""

    templates: list[str] = Field(..., description="List of registered connector types")
    count: int = Field(..., description="Total number of registered templates")


@router.post("/transform", response_model=TransformResponse)
async def transform_data(
    request: TransformRequest, _user: User = Depends(current_active_user)
):
    """
    Test a custom JSONata transformation.

    This endpoint allows testing JSONata expressions interactively without
    needing to register them as templates. Useful for developing and debugging
    new transformations.

    **Example request:**
    ```json
    {
        "jsonata_expression": "{ \\"name\\": user.name, \\"email\\": user.email }",
        "data": {
            "user": {
                "name": "John Doe",
                "email": "john@example.com"
            }
        }
    }
    ```

    **Example response:**
    ```json
    {
        "result": {
            "name": "John Doe",
            "email": "john@example.com"
        }
    }
    ```

    Args:
        request: Transform request containing JSONata expression and data
        _user: Currently authenticated user (required for access)

    Returns:
        TransformResponse containing the transformed data

    Raises:
        HTTPException: If JSONata transformation fails
    """
    try:
        result = transformer.transform_custom(request.jsonata_expression, request.data)
        logger.info(
            f"User {_user.email} tested JSONata transformation successfully"
        )
        return TransformResponse(result=result)
    except Exception as e:
        logger.error(f"JSONata transformation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"JSONata transformation failed: {str(e)}",
        ) from e


@router.get("/templates", response_model=TemplatesListResponse)
async def list_templates(_user: User = Depends(current_active_user)):
    """
    List all registered transformation templates.

    Returns the names of all connector types that have JSONata transformation
    templates registered.

    **Example response:**
    ```json
    {
        "templates": ["github", "gmail", "slack", "jira", "discord"],
        "count": 5
    }
    ```

    Args:
        _user: Currently authenticated user (required for access)

    Returns:
        TemplatesListResponse with list of template names and count
    """
    templates = transformer.list_templates()
    logger.info(f"User {_user.email} listed JSONata templates")
    return TemplatesListResponse(templates=templates, count=len(templates))


@router.get("/templates/{connector_type}", response_model=TemplateInfo)
async def check_template(
    connector_type: str, _user: User = Depends(current_active_user)
):
    """
    Check if a transformation template exists for a connector type.

    **Example response:**
    ```json
    {
        "connector_type": "github",
        "has_template": true
    }
    ```

    Args:
        connector_type: The connector type to check (e.g., 'github', 'slack')
        _user: Currently authenticated user (required for access)

    Returns:
        TemplateInfo indicating whether a template exists
    """
    has_template = transformer.has_template(connector_type)
    logger.info(
        f"User {_user.email} checked template for connector: {connector_type}"
    )
    return TemplateInfo(connector_type=connector_type, has_template=has_template)
