"""The curated local manifest: models a person picked, pinned file by file.

Evidence, not verdicts: the classifier and the support rule run over these
fields at runtime, so fixing a rule takes effect without regenerating the file.
Position in `models` is the only preference signal, most preferred first, and
nothing here is a quality score.
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.engines.audiocpp.manifest_fields import AudioDefaults
from modules.llm.catalog.local.engines.llamacpp.manifest_fields import (
    Sampling,
    ShapeSpec,
    Template,
)
from modules.llm.catalog.local.engines.registry import ENGINE_ENTRY_FIELDS, engine_for
from modules.llm.catalog.local.engines.sdcpp.manifest_fields import (
    ImageDefaults,
    VideoDefaults,
)
from modules.llm.catalog.local.manifest.strict import STRICT
from modules.llm.fit import ModelShape

SCHEMA_VERSION = 1


class Evidence(BaseModel):
    """What the classifier reads: the chosen file's own header, and the repo's tag."""

    model_config = STRICT

    architecture: str = Field(min_length=1)
    pipeline_tag: str | None = None
    parameters_b: float | None = Field(default=None, gt=0)


class ManifestFile(BaseModel):
    """One file, pinned to a commit and verified by its hash."""

    model_config = STRICT

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
    model_config = STRICT

    args: list[str] = Field(default_factory=list)


class Validated(BaseModel):
    """The runtime build a person ran this exact build on, or None."""

    model_config = STRICT

    llama_cpp: str | None = None
    sd_cpp: str | None = None
    audio_cpp: str | None = None


class ManifestBuild(BaseModel):
    model_config = STRICT

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
    model_config = STRICT

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9.\-]*$")
    name: str = Field(min_length=1)
    family: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    description: str = Field(min_length=1)
    license: str = Field(min_length=1)
    source_repo: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    evidence: Evidence
    # The trained window; a text model's only. An image model has none.
    context: int | None = Field(default=None, gt=0)
    template: Template = Field(default_factory=Template)
    sampling: Sampling | None = None
    image: ImageDefaults | None = None
    video: VideoDefaults | None = None
    audio: AudioDefaults | None = None
    # Text models only: an image model is not priced by the llama.cpp estimator.
    shape: ShapeSpec | None = None
    builds: list[ManifestBuild] = Field(min_length=1)

    @model_validator(mode="after")
    def _engine_fields(self) -> "CuratedModel":
        types = classify(self.evidence.architecture, self.evidence.pipeline_tag).types
        engine = engine_for(types)
        if engine is None:
            raise ValueError(f"{self.id}: no bundled engine runs this model")
        present = {
            name
            for name in ENGINE_ENTRY_FIELDS
            if name in self.model_fields_set and getattr(self, name) is not None
        }
        if foreign := present - engine.entry_owns:
            raise ValueError(
                f"{self.id}: {engine.name} reads none of {sorted(foreign)}"
            )
        if missing := engine.entry_requires - present:
            raise ValueError(f"{self.id}: {engine.name} needs {sorted(missing)}")
        choice = engine.entry_requires_one_of
        if choice and len(present & choice) != 1:
            raise ValueError(f"{self.id}: {engine.name} needs one of {sorted(choice)}")
        return self

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
    model_config = STRICT

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
