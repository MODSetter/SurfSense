"""The curated local manifest: models a person picked, pinned file by file.

Evidence, not verdicts: the classifier and the support rule run over these
fields at runtime, so fixing a rule takes effect without regenerating the file.
Position in `models` is the only preference signal, most preferred first, and
nothing here is a quality score.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.llm.catalog.local.builds import Build, BuildFile, FileRole
from modules.llm.fit import ModelShape

SCHEMA_VERSION = 1

_Strict = ConfigDict(extra="forbid", frozen=True)


class Evidence(BaseModel):
    """What the classifier reads: the chosen file's own header, and the repo's tag."""

    model_config = _Strict

    architecture: str = Field(min_length=1)
    pipeline_tag: str | None = None
    parameters_b: float | None = Field(default=None, gt=0)


class Template(BaseModel):
    """Read from the chat template at refresh time. None where it is silent."""

    model_config = _Strict

    tools: bool | None = None
    reasoning: bool | None = None
    system_role: bool | None = None


class SamplingSet(BaseModel):
    model_config = _Strict

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None


class Sampling(BaseModel):
    """The publisher's settings, reviewed, with where they came from."""

    model_config = _Strict

    origin: str = Field(min_length=1)
    thinking: SamplingSet | None = None
    non_thinking: SamplingSet | None = None


class ImageDefaults(BaseModel):
    model_config = _Strict

    origin: str = Field(min_length=1)
    resolution: int | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    flow_shift: float | None = None


class ShapeSpec(BaseModel):
    """The header fields the fit estimate reads, committed so an airgapped machine
    can price the row. Required widths: a missing one would price the compute
    buffer as though the model had no layers."""

    model_config = _Strict

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


class ManifestFile(BaseModel):
    """One file, pinned to a commit and verified by its hash."""

    model_config = _Strict

    role: FileRole
    repo: str = Field(min_length=1)
    # The vendor repo, when `repo` is a byte for byte mirror of it.
    upstream_repo: str | None = None
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Header keys under llama.cpp's names; a projector carries what it reads.
    gguf: dict[str, Any] = Field(default_factory=dict)


class RunArgs(BaseModel):
    model_config = _Strict

    args: list[str] = Field(default_factory=list)


class Validated(BaseModel):
    """The runtime build a person ran this exact build on, or None."""

    model_config = _Strict

    llama_cpp: str | None = None


class ManifestBuild(BaseModel):
    model_config = _Strict

    quantization: str = Field(min_length=1)
    files: list[ManifestFile] = Field(min_length=1)
    run: RunArgs = Field(default_factory=RunArgs)
    validated: Validated = Field(default_factory=Validated)

    @model_validator(mode="after")
    def _one_model(self) -> "ManifestBuild":
        roles = [f.role for f in self.files]
        if FileRole.WEIGHTS not in roles:
            raise ValueError(f"{self.quantization}: a build needs its weights")
        if roles.count(FileRole.PROJECTOR) > 1:
            raise ValueError(f"{self.quantization}: a build has one projector at most")
        return self

    def as_build(self) -> Build:
        return Build(
            self.quantization,
            tuple(
                BuildFile(
                    f.role, f.path, f.size_bytes, f.sha256, f.repo, f.revision, f.gguf
                )
                for f in self.files
            ),
        )


class CuratedModel(BaseModel):
    model_config = _Strict

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9.\-]*$")
    name: str = Field(min_length=1)
    family: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    description: str = Field(min_length=1)
    license: str = Field(min_length=1)
    source_repo: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    evidence: Evidence
    context: int = Field(gt=0)
    template: Template = Field(default_factory=Template)
    sampling: Sampling | None = None
    image: ImageDefaults | None = None
    # Text models only: an image model is not priced by the llama.cpp estimator.
    shape: ShapeSpec | None = None
    builds: list[ManifestBuild] = Field(min_length=1)

    @model_validator(mode="after")
    def _distinct_builds(self) -> "CuratedModel":
        labels = [b.quantization for b in self.builds]
        if len(labels) != len(set(labels)):
            raise ValueError(f"{self.id}: a quantization is listed twice")
        return self

    def as_builds(self) -> list[Build]:
        return [b.as_build() for b in self.builds]

    @property
    def model_shape(self) -> ModelShape | None:
        """The committed header fields as the estimator wants them, or None for
        a model the llama.cpp estimator does not price."""
        if self.shape is None:
            return None
        fields = self.shape.model_dump()
        fields["sliding_window_layers"] = tuple(fields["sliding_window_layers"])
        fields["head_count_kv_layers"] = tuple(fields["head_count_kv_layers"])
        return ModelShape(
            architecture=self.evidence.architecture,
            context_length=self.context,
            **fields,
        )


class LocalManifest(BaseModel):
    model_config = _Strict

    schema_version: int
    refreshed_at: str
    models: list[CuratedModel]

    @model_validator(mode="after")
    def _consistent(self) -> "LocalManifest":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported local manifest schema: {self.schema_version}"
            )
        ids = [m.id for m in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("a model id is listed twice")
        return self
