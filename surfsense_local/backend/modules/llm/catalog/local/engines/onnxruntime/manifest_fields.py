"""What a curated embedding model commits beyond the shared entry: what its
index's spec needs and no file states, the weight measured by the retrieval eval
among it."""

from pydantic import BaseModel, Field, model_validator

from modules.embedding.spec import Pooling
from modules.llm.catalog.local.manifest.strict import STRICT

# Cosine against the original model, per passage. granite-97m's int8 build
# measured 0.961 mean and failed; granite-311m's measured 0.990 and passed.
PARITY_MEAN = 0.99
PARITY_MIN = 0.98


class Parity(BaseModel):
    """How close a converted build's vectors are to the original model's.

    Absent for a build that is the original, which matches it by definition.
    """

    model_config = STRICT

    origin: str = Field(min_length=1)
    mean: float = Field(gt=0, le=1)
    min: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _close_enough(self) -> "Parity":
        if self.mean < PARITY_MEAN or self.min < PARITY_MIN:
            raise ValueError(
                f"parity {self.mean:.3f} mean, {self.min:.3f} min is under "
                f"{PARITY_MEAN} and {PARITY_MIN}: another vector space"
            )
        return self


class EmbeddingDefaults(BaseModel):
    model_config = STRICT

    dimension: int = Field(gt=0)
    pooling: Pooling
    normalize: bool
    query_prefix: str = ""
    document_prefix: str = ""
    max_tokens: int = Field(gt=0)
    semantic_weight: float = Field(gt=0, lt=1)
    # Peak memory is mostly the batch, not the weights, so a larger model keeps it smaller.
    batch: int = Field(gt=0)
    parity: Parity | None = None


ENTRY_OWNS = frozenset({"embedding"})
ENTRY_REQUIRES = frozenset({"embedding"})
