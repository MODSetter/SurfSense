from typing import Any

from pydantic import BaseModel

from modules.llm.model_type import ModelType


class InstallJobRead(BaseModel):
    id: str
    catalog_id: str
    label: str
    model_types: list[ModelType]
    select: bool
    model_type: ModelType | None
    # The latest install-stream frame; `complete`, `error` or `cancelled` ends it.
    event: dict[str, Any]


class InstallJobsRead(BaseModel):
    jobs: list[InstallJobRead]
