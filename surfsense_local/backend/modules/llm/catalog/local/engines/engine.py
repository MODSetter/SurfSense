"""The seam every local engine answers at: rows, its folder, install and delete steps."""

from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from modules.llm.catalog.local.build import Build, BuildFile
from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.model_type import ModelType


@dataclass(frozen=True)
class InstallStep:
    """One frame of what an engine does after the files land. `complete` ends it,
    and its message is the one the install finishes with."""

    kind: str
    message: str
    progress: float | None = None


class LocalEngine(Protocol):
    name: str
    # The selections it can fill, the first unless an install names another,
    # and the provider those selections name.
    model_types: tuple[ModelType, ...]
    provider: str

    @property
    def folder(self) -> Path | None:
        """Where its files land; None where this build does not ship it."""
        ...

    def rows(
        self,
        models: Sequence[CuratedModel],
        mint: Callable[[Build], str],
        *,
        selected: str | None,
    ) -> tuple[LocalRow, ...]: ...

    def landing(self, file: BuildFile, model_id: str) -> str:
        """Where one file of `model_id`'s build lands, relative to `folder`."""
        ...

    def holds(self, model_id: str) -> bool: ...

    def bundled(self, model_id: str) -> bool:
        """Shipped with the app, so it cannot be deleted."""
        ...

    async def check(self, plan: InstallPlan) -> InstallPlan:
        """The plan as it may install, or InstallRefusedError."""
        ...

    def after_install(self, model_id: str) -> AsyncIterator[InstallStep]: ...

    def after_remove(self) -> None: ...

    def on_startup(self) -> None: ...
