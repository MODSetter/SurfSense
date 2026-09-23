"""A build resolved for install, named by the server rather than the renderer."""

from dataclasses import dataclass

from modules.llm.catalog.local.build import Build


class InstallRefusedError(Exception):
    """A build that cannot be installed here, with the sentence a person reads."""


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
