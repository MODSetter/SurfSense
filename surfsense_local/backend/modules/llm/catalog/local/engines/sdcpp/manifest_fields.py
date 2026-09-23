"""What a curated sd.cpp model commits beyond the shared entry: how Studio
generates with it by default."""

from pydantic import BaseModel, Field

from modules.llm.catalog.local.manifest.strict import STRICT


class ImageDefaults(BaseModel):
    model_config = STRICT

    origin: str = Field(min_length=1)
    resolution: int | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    flow_shift: float | None = None


ENTRY_OWNS = frozenset({"image"})
ENTRY_REQUIRES = frozenset({"image"})
