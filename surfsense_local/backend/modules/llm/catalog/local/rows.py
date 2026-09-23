"""The one row shape every local model is shown as: curated, downloaded or searched.

The screen reads these fields and computes none of them. Nothing here carries a
position or a score; the manifest's order chooses the star and is never sent.
"""

from dataclasses import dataclass
from enum import StrEnum

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.classifier import Classification
from modules.llm.catalog.local.engines.registry import engine_for
from modules.llm.fit import Badge, FitVerdict


class LeadReason(StrEnum):
    IN_USE = "in_use"
    INSTALLED = "installed"
    RECOMMENDED = "recommended"
    FITS_SLOWER = "fits_slower"
    NOTHING_FITS = "nothing_fits"
    # An engine with no fit estimate leads with its default build.
    DEFAULT = "default"


@dataclass(frozen=True)
class Lead:
    quantization: str
    why: LeadReason


@dataclass(frozen=True)
class LocalSupport:
    """What a request to this build may carry. Images only: nothing in the app
    sends audio, so an audio projector earns nothing here."""

    context: int | None
    reads_images: bool
    tools: bool | None
    reasoning: bool | None


class Origin(StrEnum):
    CURATED = "curated"
    DOWNLOADED = "downloaded"
    SEARCH = "search"


@dataclass(frozen=True)
class BuildRow:
    catalog_id: str
    build: Build
    # None where the engine has no fit estimate: the row states the download
    # size and nothing about this machine.
    fit: FitVerdict | None
    badge: Badge | None
    # What the runtime calls the installed file, when it is on disk.
    installed_as: str | None
    recommended: bool
    reads_images: bool
    # The projector's header was read and matched the model. A listing alone
    # names a projector; only its header says it can see.
    projector_checked: bool

    @property
    def can_install(self) -> bool:
        """Only physics refuses, and only an exact figure can. An estimate
        over-charges on purpose, so it never blocks: the exact check before the
        download does."""
        if not self.catalog_id:
            return False
        return self.fit is None or self.fit.can_install or self.fit.approximate


@dataclass(frozen=True)
class LocalRow:
    id: str
    origin: Origin
    name: str
    family: str
    classification: Classification
    support: LocalSupport
    builds: tuple[BuildRow, ...]
    default_quantization: str | None
    recommended: bool
    # The engine whose catalog offered this row, which is what would run it.
    engine: str
    # The build the row shows and its Download fetches, and why. None for a
    # searched repo, which lists every build and leads with none.
    lead: Lead | None = None

    @property
    def runnable(self) -> bool:
        """The offering engine is the one that runs this type: an image model
        found through llama.cpp's search is not one sd.cpp's catalog offered."""
        engine = engine_for(self.classification.types)
        return engine is not None and engine.name == self.engine

    @property
    def not_runnable_reason(self) -> str | None:
        if self.runnable:
            return None
        return self.classification.reason or "SurfSense cannot run this model."
