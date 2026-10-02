"""Everything that decides what a vector means.

An index stores a snapshot of this, so a later edit to a manifest entry cannot
change what an existing index's vectors are.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Source(StrEnum):
    CURATED = "curated"
    HUGGINGFACE = "huggingface"
    REMOTE = "remote"


class Identified(StrEnum):
    """How SurfSense knows the model is built to embed."""

    MEASURED = "measured"
    DECLARED = "declared"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"


class Pooling(StrEnum):
    CLS = "cls"
    MEAN = "mean"
    LAST = "last"
    # The build pools inside its own graph and returns one vector per text.
    IN_MODEL = "in_model"


class PinnedFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EmbedderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    source: Source
    identified: Identified
    repo: str = Field(min_length=1)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    weights: PinnedFile
    tokenizer: PinnedFile
    dimension: int = Field(gt=0)
    pooling: Pooling
    normalize: bool
    query_prefix: str = ""
    document_prefix: str = ""
    max_tokens: int = Field(gt=0)
    semantic_weight: float = Field(gt=0, lt=1)
    # Passages embedded at once; the batch, not the weights, sets peak memory.
    batch: int = Field(default=32, gt=0)
