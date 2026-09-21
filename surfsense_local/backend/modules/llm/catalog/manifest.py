"""The curated manifest: models SurfSense has tested, priced offline.

**Source, not build output.** A person runs the authoring script, reads what it
proposes, and commits the result. That is deliberate: a rank moving 78 to 94
shows up in a pull request where someone notices, a tag rebuilds to the same
manifest forever, and the cadence is honest, since these change when someone
adds a model rather than when someone cuts a release.

The schema enforces one thing no reviewer reliably catches: a `rank` sits inside
the variant it was measured on, so it cannot describe a build the manifest does
not ship.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.llm.fit import ModelShape

SCHEMA_VERSION = 4


class ModelShapeSpec(BaseModel):
    """Header fields, committed so an airgapped machine can price the row.

    Quantization independent: measured, the architecture fields are identical
    across Q4_K_M, Q8_0 and f16 of the same model, so one header read at
    authoring time prices every build of it forever.
    """

    model_config = ConfigDict(extra="forbid")

    architecture: str = Field(min_length=1)
    block_count: int = Field(gt=0)
    head_count_kv: int = Field(gt=0)
    key_length: int = Field(gt=0)
    value_length: int = Field(gt=0)
    context_length: int = Field(gt=0)
    n_vocab: int = Field(gt=0)

    # Required, unlike the optional fields on `ModelShape`. A committed entry is
    # authored by a script that read a real header, so a missing width here is a
    # manifest written by hand or by an older script, and the compute buffer
    # would quietly price it as though the model had no layers to compute. The
    # app refuses to start on that rather than shipping a confident wrong badge.
    embedding_length: int = Field(gt=0)
    feed_forward_length: int = Field(gt=0)

    sliding_window: int = Field(default=0, ge=0)
    expert_count: int = Field(default=0, ge=0)
    expert_feed_forward_length: int = Field(default=0, ge=0)
    expert_shared_feed_forward_length: int = Field(default=0, ge=0)
    expert_used_count: int = Field(default=0, ge=0)
    sliding_window_pattern: int = Field(default=0, ge=0)
    sliding_window_layers: list[bool] = Field(default_factory=list)
    shared_kv_layers: int = Field(default=0, ge=0)
    kv_lora_rank: int = Field(default=0, ge=0)
    key_length_mla: int = Field(default=0, ge=0)


class Variant(BaseModel):
    """One downloadable build, plus the three fields a person decides.

    Everything above `rank` is derived from the Hugging Face listing and the
    GGUF header. Everything from `rank` down is judgement, and it lives here
    rather than on the entry because quality is a function of (model,
    quantization), not of the model alone.
    """

    model_config = ConfigDict(extra="forbid")

    repo: str = Field(min_length=1)
    file: str = Field(min_length=1)
    quantization: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)
    mmproj: str | None = None

    rank: int = Field(gt=0)
    rank_basis: str = Field(min_length=1)
    validated: bool = False


class CuratedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    label: str = Field(min_length=1)
    parameter_count: str = Field(min_length=1)

    shape: ModelShapeSpec
    # User facing only. Today that means "vision" or nothing; everything else
    # the template reports is an internal constraint, not a badge.
    capabilities: list[str] = Field(default_factory=list)
    # Fraction of the build's bytes read per decoded token: 1.0 dense, the
    # active slice for a mixture of experts. Per model rather than per variant,
    # because it is an expert to total byte ratio and barely moves with quant.
    decode_fraction: float = Field(default=1.0, gt=0.0, le=1.0)

    # A list from the start, with one thing in it. Costs nothing now and is the
    # only part of this schema that is expensive to add later, because changing
    # it means a schema version bump and re-authoring every entry.
    variants: list[Variant] = Field(min_length=1)

    @property
    def model_shape(self) -> ModelShape:
        """The committed header fields, as the estimator wants them.

        This is what lets a curated row be priced on first paint with no network
        and nothing downloaded.
        """
        fields = self.shape.model_dump()
        # JSON has no tuples and the shape is frozen, so the one list field is
        # converted here rather than leaving a mutable member on a frozen value.
        fields["sliding_window_layers"] = tuple(fields["sliding_window_layers"])
        return ModelShape(**fields)


class CuratedModelsManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    models: list[CuratedModel]

    @model_validator(mode="after")
    def validate_manifest(self) -> "CuratedModelsManifest":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported curated-model schema: {self.schema_version}")

        ids = [model.model_id for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate model_id in curated-model manifest")

        files = [
            (variant.repo, variant.file)
            for model in self.models
            for variant in model.variants
        ]
        if len(files) != len(set(files)):
            raise ValueError("duplicate pinned file in curated-model manifest")

        bases = {
            variant.rank_basis
            for model in self.models
            for variant in model.variants
        }
        if len(bases) > 1:
            raise ValueError(
                "ranks from different rank_basis values cannot be compared: "
                f"{sorted(bases)}"
            )
        return self


def load_curated_models(path: Path | None = None) -> CuratedModelsManifest:
    manifest_path = path or Path(__file__).with_name("curated-models.json")
    return CuratedModelsManifest.model_validate_json(manifest_path.read_text())
