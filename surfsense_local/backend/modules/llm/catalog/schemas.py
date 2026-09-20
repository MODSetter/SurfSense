"""What the model screen receives.

Two things are deliberately absent from every row: a `rank`, and any hint of a
scan. Rank orders the curated list and selects the star and is never displayed,
so the renderer does not receive it. There is no `scanned` flag because there is
no scan: the budget comes from the runtime's own allocator in milliseconds.
"""

from pydantic import BaseModel, ConfigDict, Field


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


class BadgeRead(BaseModel):
    """A verdict plus one plain line of why."""

    verdict: str
    reason: str


class FitRead(BaseModel):
    state: str
    need_bytes: int
    budget_bytes: int
    # Kept on the wire because the reason line is graded by it and the renderer
    # must not recompute it. Three buckets lose the difference between a model
    # that spills 5% and one that spills 70%.
    offload_fraction: float
    approximate: bool = False


class CatalogRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    catalog_id: str
    model_id: str
    # What the runtime calls the installed file, which is what Use and Delete
    # act on. Distinct from `model_id`, which identifies the model rather than
    # the build, and from `catalog_id`, which is an opaque install token.
    variant_model_id: str
    label: str
    family: str
    parameter_count: str
    quantization: str
    size_bytes: int
    context_length: int
    fit: FitRead
    badge: BadgeRead
    capabilities: list[str]
    installed: bool
    selected: bool
    can_install: bool
    recommended: bool


class InstalledRowRead(BaseModel):
    model_id: str
    file: str
    size_bytes: int
    selected: bool


class CatalogRead(BaseModel):
    budget: BudgetRead
    curated: list[CatalogRowRead]
    installed: list[InstalledRowRead]
    recommended_model_id: str | None


class SearchRowRead(BaseModel):
    """A repo, described. No rank and no quality claim, ever."""

    repo: str
    downloads: int
    likes: int
    license: str | None
    gated: bool
    quantized_from: str | None
    last_modified: str | None


class SearchRead(BaseModel):
    results: list[SearchRowRead]


class BuildRead(BaseModel):
    """One installable build inside a repo, priced exactly."""

    catalog_id: str
    file: str
    quantization: str
    size_bytes: int
    fit: FitRead
    badge: BadgeRead
    can_install: bool


class RepoRead(BaseModel):
    repo: str
    architecture: str
    context_length: int
    supported: bool
    builds: list[BuildRead]
    # Eligibility is not fit: a model can be FITS and still refused here, and the
    # two must never render as one thing.
    ineligible_reason: str | None = None


class InstallRequest(BaseModel):
    catalog_id: str = Field(min_length=1, max_length=128)
    select: bool = True
