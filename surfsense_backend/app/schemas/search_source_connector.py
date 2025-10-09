import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.db import SearchSourceConnectorType
from app.utils.validators import validate_connector_config

from .base import IDModel, TimestampModel


class SearchSourceConnectorBase(BaseModel):
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: datetime | None = None
    config: dict[str, Any]

    @field_validator("config")
    @classmethod
    def validate_config_for_connector_type(
        cls, config: dict[str, Any], values: dict[str, Any]
    ) -> dict[str, Any]:
        connector_type = values.data.get("connector_type")
        return validate_connector_config(connector_type, config)


class SearchSourceConnectorCreate(SearchSourceConnectorBase):
    pass


class SearchSourceConnectorUpdate(BaseModel):
    name: str | None = None
    connector_type: SearchSourceConnectorType | None = None
    is_indexable: bool | None = None
    last_indexed_at: datetime | None = None
    config: dict[str, Any] | None = None


class SearchSourceConnectorRead(SearchSourceConnectorBase, IDModel, TimestampModel):
    search_space_id: int
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
