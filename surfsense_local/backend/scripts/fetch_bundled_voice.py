"""Stage the voice the installer ships, so podcasts work from the first start.

`uv run scripts/fetch_bundled_voice.py` places it where the app reads it in
development; pass a models root (`... models`) to stage it for an installer,
which electron-builder copies into resources/models. The file lands as a
catalog install does: from its pinned commit, sha256-checked, with its record.
"""

import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.audiocpp import ENGINE
from modules.llm.catalog.local.engines.audiocpp.builds.choice import default_build
from modules.llm.catalog.local.engines.audiocpp.bundled import (
    BUNDLED_DIR_NAME,
    bundled_audio_dir,
)
from modules.llm.catalog.local.install.download import download_build
from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.installs import read_installs
from modules.llm.catalog.local.manifest import CuratedModel, load_local_manifest


def shipped_build(models: Sequence[CuratedModel]) -> Build:
    """The manifest's first audio model, in its default build."""
    model = next(m for m in models if m.audio is not None)
    build = default_build(model.as_builds())
    if build is None:
        raise ValueError(f"{model.id} has no build to ship")
    return build


async def stage(
    build: Build, into: Path, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    plan = InstallPlan(build.runtime_name, build, ENGINE)
    async for _ in download_build(plan, into, transport=transport):
        pass


def main() -> int:
    # Optional models root for staging an installer; defaults to the dev location.
    into = (
        Path(sys.argv[1]) / BUNDLED_DIR_NAME
        if len(sys.argv) > 1
        else bundled_audio_dir()
    )
    build = shipped_build(load_local_manifest().models)
    name = build.weights.path.rsplit("/", 1)[-1]
    record = read_installs(into).get(build.runtime_name)
    if record and record.revision == build.weights.revision and (into / name).exists():
        print(f"have {into / name}")
        return 0
    print(f"get  {name}")
    asyncio.run(stage(build, into))
    return 0


if __name__ == "__main__":
    sys.exit(main())
