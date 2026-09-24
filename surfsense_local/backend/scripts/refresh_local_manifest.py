"""Rewrite the curated local manifest from Hugging Face, pinned to commits.

Run by hand, never in CI and never at packaging:

    uv run scripts/refresh_local_manifest.py [--accept-loss] [--only ID ...]

A person reads the diff and commits it. `local_manifest/entries.py` is the only
hand-authored input: which models, in which order. For each, this reads the
repo at its current commit, pins every build in its engine's preference order
with its hash, and reads the default build's header (and a projector's) over
HTTP range requests. No weights are downloaded. Each engine's `refresh.py`
holds its `VALIDATED` builds. `--only` refreshes the named entries and keeps
every other one exactly as the manifest has it, so adding a model does not
re-pin the rest.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

import httpx
from local_manifest.audiocpp import refresh as audiocpp
from local_manifest.audiocpp.entry import AudioEntry
from local_manifest.entries import ENTRIES
from local_manifest.guard import losses
from local_manifest.llamacpp import refresh as llamacpp
from local_manifest.sdcpp import refresh as sdcpp
from local_manifest.sdcpp.entry import ImageEntry
from local_manifest.unreadable import UnreadableBuildError

from modules.llm.catalog.local.manifest import (
    MANIFEST_PATH,
    SCHEMA_VERSION,
    LocalManifest,
)


def _engine(entry):
    if isinstance(entry, AudioEntry):
        return audiocpp
    return sdcpp if isinstance(entry, ImageEntry) else llamacpp


async def build(only: set[str] | None = None) -> dict:
    kept = {}
    if only is not None:
        kept = {m["id"]: m for m in json.loads(MANIFEST_PATH.read_text())["models"]}
        if unknown := only - {e.id for e in ENTRIES}:
            raise UnreadableBuildError(f"no entry named {sorted(unknown)}")
    models = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        for entry in ENTRIES:
            if only is not None and entry.id not in only:
                if entry.id not in kept:
                    raise UnreadableBuildError(
                        f"{entry.id} is not in the manifest yet; refresh it too"
                    )
                models.append(kept[entry.id])
                continue
            models.append(await _engine(entry).refresh(client, entry))
    return {
        "schema_version": SCHEMA_VERSION,
        "refreshed_at": datetime.now(UTC).date().isoformat(),
        "models": models,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--accept-loss",
        action="store_true",
        help="write even though models or builds disappeared",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="ID",
        help="refresh these entries and keep the rest as written",
    )
    arguments = parser.parse_args()
    accept_loss = arguments.accept_loss
    only = set(arguments.only) if arguments.only else None

    print("reading listings and headers, pinned to each repo's commit:")
    try:
        proposed = asyncio.run(build(only))
    except UnreadableBuildError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1

    LocalManifest.model_validate(proposed)
    if MANIFEST_PATH.exists() and not accept_loss:
        problems = losses(json.loads(MANIFEST_PATH.read_text()), proposed)
        if problems:
            print("refused, rerun with --accept-loss to write anyway:", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 1

    MANIFEST_PATH.write_text(json.dumps(proposed, indent=2) + "\n")
    total = sum(len(m["builds"]) for m in proposed["models"])
    print(
        f"\nwrote {MANIFEST_PATH.name}: {len(proposed['models'])} models, {total} builds"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
