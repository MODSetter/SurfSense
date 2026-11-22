"""Which job packs the configured store would serve, and why the rest are refused.

    python -m license.scripts.list_job_packs

Reads the store the server reads (JOB_PACKS_DIR, or JOB_PACKS_GITHUB_REPO with
JOB_PACKS_GITHUB_TOKEN), downloads every pack and checks it as the route does,
with the same compiled keys. Exits 1 when no store is set, the store cannot be
read, or nothing passes. Never prints the token.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from license.job_packs.catalog import configured_source
from license.job_packs.manifest import PackRefusedError
from license.job_packs.source import PackSourceError
from license.job_packs.verify import verified_pack


async def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        prog="list_job_packs", description=__doc__.split("\n\n")[0]
    ).parse_args(argv)
    source = configured_source()
    if source is None:
        print(
            "No job pack store is set: set JOB_PACKS_DIR, or JOB_PACKS_GITHUB_REPO "
            "and JOB_PACKS_GITHUB_TOKEN.",
            file=sys.stderr,
        )
        return 1
    try:
        assets = await source.assets()
    except PackSourceError as error:
        print(f"The job pack store cannot be read: {error}", file=sys.stderr)
        return 1

    passed = 0
    for asset in assets:
        try:
            pack = verified_pack(await source.read(asset), name=asset.name)
        except PackRefusedError as refused:
            print(f"{asset.name}: refused, {refused.code}: {refused.message}")
            continue
        except PackSourceError as error:
            print(f"{asset.name}: not downloaded: {error}")
            continue
        passed += 1
        for job in pack.jobs:
            print(
                f"{pack.id} {pack.version}: {job.key} ({job.runner}) "
                f"for {job.entitlement}"
            )
    if not passed:
        print("No job pack passes its checks, so none is served.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
