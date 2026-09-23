"""Rewrite the curated local manifest from Hugging Face, pinned to commits.

Run by hand, never in CI and never at packaging:

    uv run scripts/refresh_local_manifest.py [--accept-loss]

A person reads the diff and commits it. `local_manifest/entries.py` is the only
hand-authored input: which models, in which order. For each, this reads the
repo at its current commit, pins every build in the quantization preference
order with its hash, and reads the default build's header (and its projector's)
over HTTP range requests. No weights are downloaded.

`VALIDATED` names builds somebody downloaded, chatted with and confirmed
citations resolve on, with the llama.cpp build they ran it on.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

import httpx
from local_manifest.assemble import UnreadableBuildError, entry_for, pinned_builds
from local_manifest.entries import ENTRIES
from local_manifest.guard import losses
from local_manifest.hub import header, repo_at_revision

from modules.llm.catalog.local.engines.llamacpp.builds.choice import default_build
from modules.llm.catalog.local.manifest import (
    MANIFEST_PATH,
    SCHEMA_VERSION,
    LocalManifest,
)

# weights path -> the llama.cpp build a person ran it on
VALIDATED: dict[str, str] = {}


async def build() -> dict:
    models = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        for entry in ENTRIES:
            snapshot = await repo_at_revision(client, entry.repo)
            builds = pinned_builds(snapshot)
            chosen = default_build(builds)
            if chosen is None:
                raise UnreadableBuildError(
                    f"{entry.repo}: no build in the preference order"
                )
            weights = await header(
                client, entry.repo, snapshot.revision, chosen.weights.path
            )
            projector = (
                await header(
                    client, entry.repo, snapshot.revision, chosen.projector.path
                )
                if chosen.projector
                else None
            )
            written = entry_for(entry, snapshot, builds, weights, projector, VALIDATED)
            print(
                f"  {entry.name:12s} {snapshot.revision[:8]}  {len(builds):2d} builds, "
                f"default {chosen.quantization}"
                + (", reads images" if projector else "")
            )
            models.append(written)
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
    accept_loss = parser.parse_args().accept_loss

    print("reading listings and headers, pinned to each repo's commit:")
    try:
        proposed = asyncio.run(build())
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
