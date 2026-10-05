"""A build resolved for install, named by the server rather than the renderer."""

from dataclasses import dataclass

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.classifier import NotRunnableCode
from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.fit import ModelShape


class InstallRefusedError(Exception):
    """A build that cannot be installed here, with the sentence a person reads.

    `code` names the reason where the interface has its own words for it: an
    install's own, or the classifier's for a file that is not a chat model.
    `values` are the raw numbers those words take."""

    def __init__(
        self,
        message: str,
        code: InstallCode | NotRunnableCode | None = None,
        **values: int,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.values = values


@dataclass(frozen=True)
class InstallPlan:
    model_id: str
    build: Build
    # The engine that runs it, which decides where its files land.
    engine: str
    # A searched build is read exactly before it downloads; a curated one was
    # read when the manifest was refreshed.
    needs_check: bool = False
    pipeline_tag: str | None = None
    # A curated chat build's committed shape, so whether it fits here is priced
    # from the manifest, as its row is, with no header read.
    shape: ModelShape | None = None
