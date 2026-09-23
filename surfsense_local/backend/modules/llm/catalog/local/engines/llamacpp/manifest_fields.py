"""What a curated llama.cpp model commits beyond the shared entry: its chat
template, its publisher's sampling, and the header fields fit prices it from."""

from pydantic import BaseModel, Field

from modules.llm.catalog.local.manifest.strict import STRICT


class Template(BaseModel):
    """Read from the chat template at refresh time. None where it is silent."""

    model_config = STRICT

    tools: bool | None = None
    reasoning: bool | None = None
    system_role: bool | None = None


class SamplingSet(BaseModel):
    model_config = STRICT

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None


class Sampling(BaseModel):
    """The publisher's settings, reviewed, with where they came from."""

    model_config = STRICT

    origin: str = Field(min_length=1)
    thinking: SamplingSet | None = None
    non_thinking: SamplingSet | None = None


class ShapeSpec(BaseModel):
    """The header fields the fit estimate reads, committed so an airgapped machine
    can price the row. Required widths: a missing one would price the compute
    buffer as though the model had no layers."""

    model_config = STRICT

    block_count: int = Field(gt=0)
    head_count_kv: int = Field(gt=0)
    key_length: int = Field(gt=0)
    value_length: int = Field(gt=0)
    n_vocab: int = Field(gt=0)
    embedding_length: int = Field(gt=0)
    feed_forward_length: int = Field(gt=0)
    sliding_window: int = Field(default=0, ge=0)
    expert_count: int = Field(default=0, ge=0)
    expert_feed_forward_length: int = Field(default=0, ge=0)
    expert_shared_feed_forward_length: int = Field(default=0, ge=0)
    expert_used_count: int = Field(default=0, ge=0)
    sliding_window_pattern: int = Field(default=0, ge=0)
    sliding_window_layers: list[bool] = Field(default_factory=list)
    key_length_swa: int = Field(default=0, ge=0)
    value_length_swa: int = Field(default=0, ge=0)
    head_count_kv_layers: list[int] = Field(default_factory=list)
    shared_kv_layers: int = Field(default=0, ge=0)
    kv_lora_rank: int = Field(default=0, ge=0)
    key_length_mla: int = Field(default=0, ge=0)


# The entry fields llama.cpp reads, and the one it cannot run without.
ENTRY_OWNS = frozenset({"context", "template", "sampling", "shape"})
ENTRY_REQUIRES = frozenset({"context"})
