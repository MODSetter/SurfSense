"""What the model screen receives for local models.

One row shape for curated, downloaded and searched models, so the screen reads
the same fields whatever a row's origin. Absent on purpose: any quality score or
list position. The screen renders these fields and computes none of them.
"""

from pydantic import BaseModel, Field

from modules.llm.model_type import ModelType


class DeviceRead(BaseModel):
    name: str
    description: str
    kind: str
    total_bytes: int
    free_bytes: int


class BudgetRead(BaseModel):
    """One device, never a sum across devices."""

    device_total_bytes: int
    device_free_bytes: int
    usable_vram_bytes: int
    fit_reserve_bytes: int
    ram_available_bytes: int
    uma: bool
    has_gpu: bool


class SystemRead(BaseModel):
    budget: BudgetRead
    devices: list[DeviceRead]
    gpu_status: str


class BadgeRead(BaseModel):
    """A warning, when there is one. `none` means there is nothing to flag,
    and then `verdict` is empty; `reason` may still describe the fit quietly."""

    level: str
    verdict: str
    reason: str


class FitRead(BaseModel):
    state: str
    need_bytes: int
    budget_bytes: int
    # The reason line is graded by it; the renderer must not recompute it.
    offload_fraction: float
    # Estimated from the listing's sizes. Checked exactly before a download.
    approximate: bool = False


class FileRead(BaseModel):
    role: str
    path: str
    size_bytes: int


class BuildRead(BaseModel):
    # Opaque install token; empty for a build that cannot be installed here.
    catalog_id: str
    quantization: str
    footprint_bytes: int
    # What Download fetches, less files another model already brought; null
    # where nothing is shared, so the footprint is the download.
    download_bytes: int | None = None
    files: list[FileRead]
    # Null where the engine has no fit estimate (image models): the row states
    # the download size and nothing about this machine.
    fit: FitRead | None
    badge: BadgeRead | None
    can_install: bool
    # What the runtime calls this build on disk, which Use and Delete act on.
    installed_as: str | None
    selected: bool
    recommended: bool
    reads_images: bool
    projector_checked: bool
    # Comes with the app: installed from the first start, with no Delete.
    bundled: bool


class LeadRead(BaseModel):
    """The build a row shows and its Download fetches, and why it is that one:
    `in_use`, `installed`, `recommended`, `fits_slower` or `nothing_fits`."""

    quantization: str
    why: str


class SupportRead(BaseModel):
    context: int | None
    reads_images: bool
    tools: bool | None
    reasoning: bool | None


class VoicingRead(BaseModel):
    peak_mb: int
    voice_count: int
    languages: list[str]


class LocalRowRead(BaseModel):
    id: str
    source: str = "local"
    origin: str
    name: str
    family: str
    types: list[ModelType]
    known: bool
    approximate: bool
    selectable_for: list[ModelType]
    support: SupportRead
    runnable: bool
    not_runnable_reason: str | None
    builds: list[BuildRead]
    default_quantization: str | None
    recommended: bool
    # The engine that offered the row and would run it: llamacpp, sdcpp or audiocpp.
    engine: str
    # Absent for a searched repo, which lists every build and leads with none.
    lead: LeadRead | None
    # An audio model's memory while voicing, voices and languages; null otherwise.
    voicing: VoicingRead | None = None


class LocalCatalogRead(BaseModel):
    budget: BudgetRead
    gpu_status: str
    rows: list[LocalRowRead]
    recommended_id: str | None


class SearchHitRead(BaseModel):
    """A repo, described. No quality claim, ever."""

    repo: str
    downloads: int
    likes: int
    license: str | None
    gated: bool
    # The repo it was quantized from, from its `base_model:quantized:` tag.
    # Provenance, returned for callers and deliberately not shown on the row.
    quantized_from: str | None
    last_modified: str | None
    # Judged by the repo's file names; the header read before install decides.
    reads_images: bool


class SearchRead(BaseModel):
    results: list[SearchHitRead]


class RepoRead(BaseModel):
    repo: str
    gated: bool
    row: LocalRowRead


class InstallRequest(BaseModel):
    catalog_id: str = Field(min_length=1, max_length=128)
    select: bool = True
