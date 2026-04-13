"""Create the Daytona snapshot used by SurfSense sandboxes.

Usage:
    uv run python scripts/create_sandbox_snapshot.py

Requires DAYTONA_API_KEY (and optionally DAYTONA_API_URL / DAYTONA_TARGET)
to be set in the environment or in a .env file.
"""

import os
import sys

from daytona import CreateSnapshotParams, Daytona, DaytonaConfig, Image

SNAPSHOT_NAME = "surfsense-sandbox"

PACKAGES = [
    "pandas",
    "numpy",
    "matplotlib",
    "scipy",
    "scikit-learn",
]


def main() -> None:
    config = DaytonaConfig(
        api_key=os.environ.get("DAYTONA_API_KEY", ""),
        api_url=os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
        target=os.environ.get("DAYTONA_TARGET", "us"),
    )
    daytona = Daytona(config)

    image = (
        Image.debian_slim("3.12")
        .pip_install(*PACKAGES)
        # The agent's virtual filesystem serves documents at /documents/.
        # This symlink lets code inside the sandbox use the same path.
        .run("mkdir -p /home/daytona/documents && ln -sf /home/daytona/documents /documents")
    )

    print(f"Creating snapshot '{SNAPSHOT_NAME}' with packages: {', '.join(PACKAGES)}")
    snapshot = daytona.snapshot.create(
        CreateSnapshotParams(name=SNAPSHOT_NAME, image=image),
        on_logs=lambda chunk: print(chunk, end=""),
    )
    print(f"\nSnapshot created: {snapshot.name}")
    print(f"Set DAYTONA_SNAPSHOT_ID={snapshot.name} in your .env")


if __name__ == "__main__":
    sys.exit(main() or 0)
