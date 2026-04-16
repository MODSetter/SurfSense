"""Create the Daytona snapshot used by SurfSense code-execution sandboxes.

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/create_sandbox_snapshot.py

Prerequisites:
    - DAYTONA_API_KEY set in surfsense_backend/.env (or exported in shell)
    - DAYTONA_API_URL=https://app.daytona.io/api
    - DAYTONA_TARGET=us  (or eu)

After this script succeeds, add to surfsense_backend/.env:
    DAYTONA_SNAPSHOT_ID=surfsense-sandbox
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).parent
for candidate in [
    _here / "../surfsense_backend/.env",
    _here / ".env",
    _here / "../.env",
]:
    if candidate.exists():
        load_dotenv(candidate)
        break

from daytona import CreateSnapshotParams, Daytona, Image  # noqa: E402

SNAPSHOT_NAME = "surfsense-sandbox"

PACKAGES = [
    "pandas",
    "numpy",
    "matplotlib",
    "scipy",
    "scikit-learn",
]


def build_image() -> Image:
    """Build the sandbox image with data-science packages and a /documents symlink."""
    return (
        Image.debian_slim("3.12")
        .pip_install(*PACKAGES)
        # Symlink /documents → /home/daytona/documents so the LLM can use
        # the same /documents/ path it sees in the virtual filesystem.
        .run_commands(
            "mkdir -p /home/daytona/documents",
            "ln -sfn /home/daytona/documents /documents",
        )
    )


def main() -> None:
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        print("ERROR: DAYTONA_API_KEY is not set.", file=sys.stderr)
        print(
            "Add it to surfsense_backend/.env or export it in your shell.",
            file=sys.stderr,
        )
        sys.exit(1)

    daytona = Daytona()

    try:
        existing = daytona.snapshot.get(SNAPSHOT_NAME)
        print(f"Deleting existing snapshot '{SNAPSHOT_NAME}' …")
        daytona.snapshot.delete(existing)
        print(f"Deleted '{SNAPSHOT_NAME}'. Waiting for removal to propagate …")
        for _attempt in range(30):
            time.sleep(2)
            try:
                daytona.snapshot.get(SNAPSHOT_NAME)
            except Exception:
                print(f"Confirmed '{SNAPSHOT_NAME}' is gone.\n")
                break
        else:
            print(
                f"WARNING: '{SNAPSHOT_NAME}' may still exist after 60s. Proceeding anyway.\n"
            )
    except Exception:
        pass

    print(f"Building snapshot '{SNAPSHOT_NAME}' …")
    print(f"Packages: {', '.join(PACKAGES)}\n")

    daytona.snapshot.create(
        CreateSnapshotParams(name=SNAPSHOT_NAME, image=build_image()),
        on_logs=lambda chunk: print(chunk, end="", flush=True),
    )

    print(f"\n\nSnapshot '{SNAPSHOT_NAME}' is ready.")
    print("\nAdd this to surfsense_backend/.env:")
    print(f"    DAYTONA_SNAPSHOT_ID={SNAPSHOT_NAME}")


if __name__ == "__main__":
    main()
