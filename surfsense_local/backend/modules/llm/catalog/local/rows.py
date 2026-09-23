"""The one row shape every local model is shown as: curated, downloaded or searched.

The screen reads these fields and computes none of them. Nothing here carries a
position or a score; the manifest's order chooses the star and is never sent.
"""

from dataclasses import dataclass
from enum import StrEnum

from modules.llm.catalog.local.builds import Build
from modules.llm.catalog.local.classifier import Classification
from modules.llm.catalog.local.support import LocalSupport
from modules.llm.fit import Badge, FitVerdict
from modules.llm.model_type import ModelType


class Origin(StrEnum):
    CURATED = "curated"
    DOWNLOADED = "downloaded"
    SEARCH = "search"


@dataclass(frozen=True)
class BuildRow:
    catalog_id: str
    build: Build
    fit: FitVerdict
    badge: Badge
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
        return bool(self.catalog_id) and (self.fit.can_install or self.fit.approximate)


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

    @property
    def runnable(self) -> bool:
        """The bundled runtime chats, so only a text model runs here."""
        return ModelType.TEXT_GEN in self.classification.types

    @property
    def not_runnable_reason(self) -> str | None:
        if self.runnable:
            return None
        return self.classification.reason or "SurfSense cannot run this model."
