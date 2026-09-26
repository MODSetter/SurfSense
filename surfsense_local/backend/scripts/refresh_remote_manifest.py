"""Rewrite the remote model manifest from models.dev.

Run by hand, never in CI and never at packaging:

    uv run scripts/refresh_remote_manifest.py [--accept-shrink]

A person reads the diff and commits it. Packaging bundles the committed file,
so an unreviewed upstream change never ships and an old tag rebuilds the same
app. Nothing fetches models.dev at runtime.

What the file keeps, and why, is in docs/proposals/model-catalog.md. The
translation is `remote_manifest/translate.py`; this file only fetches, guards,
validates and writes.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from remote_manifest.endpoints import stale_endpoints
from remote_manifest.guard import shrinkage
from remote_manifest.render import render
from remote_manifest.translate import translate

from modules.llm.catalog.remote.manifest.schema import SCHEMA_VERSION, RemoteManifest

SOURCE = "https://models.dev/api.json"
TARGET = (
    Path(__file__).resolve().parents[1]
    / "modules/llm/catalog/remote/manifest/models.json"
)


def _sorted(manifest: dict) -> dict:
    """Stable order, so a refresh diff shows what changed and nothing else."""
    return {
        "providers": {
            name: {
                **provider,
                "models": dict(sorted(provider["models"].items())),
            }
            for name, provider in sorted(manifest["providers"].items())
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--accept-shrink",
        action="store_true",
        help="write even though providers or many models disappeared",
    )
    accept_shrink = parser.parse_args().accept_shrink

    try:
        api = httpx.get(SOURCE, timeout=60.0, follow_redirects=True).json()
    except (httpx.HTTPError, ValueError) as error:
        print(f"error: could not read models.dev: {error}", file=sys.stderr)
        return 1

    for provider in stale_endpoints(api):
        print(f"warning: reviewed endpoint for {provider} has no provider in models.dev")

    proposed = _sorted(translate(api))
    if TARGET.exists():
        problems = shrinkage(json.loads(TARGET.read_text()), proposed)
        if problems and not accept_shrink:
            for problem in problems:
                print(f"refused: {problem}", file=sys.stderr)
            print("rerun with --accept-shrink once you have checked why", file=sys.stderr)
            return 1

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "refreshed_at": datetime.now(UTC).date().isoformat(),
        **proposed,
    }
    # Fail here rather than shipping something the app would reject at startup.
    RemoteManifest.model_validate(manifest)
    TARGET.write_text(render(manifest))

    providers = manifest["providers"]
    models = sum(len(provider["models"]) for provider in providers.values())
    print(f"wrote {len(providers)} providers and {models} models to {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
