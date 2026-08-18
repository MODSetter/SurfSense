"""Register the published sandbox image as the Daytona snapshot.

Both providers run the same image, built from docker/sandbox/Dockerfile and
pushed by CI. OpenSandbox pulls it onto the host docker daemon; Daytona pulls
it into a snapshot, which is what this script creates.

Run from the backend directory:
    cd surfsense_backend
    uv run python scripts/create_sandbox_snapshot.py ghcr.io/modsetter/surfsense-sandbox:<version>

The argument may be omitted when SANDBOX_IMAGE names a pinned tag.

Prerequisites:
    - DAYTONA_API_KEY set in surfsense_backend/.env (or exported in shell)
    - DAYTONA_API_URL=https://app.daytona.io/api
    - DAYTONA_TARGET=us  (or eu)
    - the image is public, or its registry is registered in the Daytona dashboard

After this script succeeds, add to surfsense_backend/.env:
    DAYTONA_SNAPSHOT_ID=surfsense-sandbox
"""

import os
import sys
import time
from pathlib import Path

from daytona import CreateSnapshotParams, Daytona, Resources
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

SNAPSHOT_NAME = "surfsense-sandbox"

# The image unpacks well past the 3 GiB Daytona's smallest default allows.
DISK_GIB = 10

# Daytona resolves the reference once, at snapshot creation, and never re-pulls
# it, so a moving tag would freeze whatever it happened to see first. Daytona
# rejects these outright rather than let that happen quietly.
UNPINNED_TAGS = frozenset({"latest", "lts", "stable"})


def resolve_image(argv: list[str], environ: dict[str, str]) -> str:
    """Validate the image reference to snapshot, from argv or SANDBOX_IMAGE."""
    image = (argv[1] if len(argv) > 1 else environ.get("SANDBOX_IMAGE", "")).strip()
    if not image:
        raise SystemExit(
            "ERROR: pass the sandbox image, or set SANDBOX_IMAGE to a pinned tag."
        )
    # Only the last path segment can carry the tag; a registry host may hold a
    # colon of its own for a port.
    name = image.rpartition("/")[2]
    if "@" in name:
        return image
    _, separator, tag = name.partition(":")
    if not separator:
        raise SystemExit(
            f"ERROR: {image} has no tag. Daytona requires a tag or digest."
        )
    if tag in UNPINNED_TAGS:
        raise SystemExit(
            f"ERROR: Daytona rejects the '{tag}' tag. Pass a release version instead."
        )
    return image


def main() -> None:
    image = resolve_image(sys.argv, os.environ)

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

    print(f"Building snapshot '{SNAPSHOT_NAME}' from {image} …\n")

    daytona.snapshot.create(
        CreateSnapshotParams(
            name=SNAPSHOT_NAME,
            image=image,
            # The image boots the OpenSandbox Jupyter stack, which Daytona has
            # no use for: it injects its own daemon and needs only a live
            # container. Set explicitly because Daytona's dropping of inherited
            # entrypoints is a bug they intend to fix (daytonaio/daytona#3853).
            entrypoint=["sleep", "infinity"],
            resources=Resources(disk=DISK_GIB),
        ),
        on_logs=lambda chunk: print(chunk, end="", flush=True),
    )

    print(f"\n\nSnapshot '{SNAPSHOT_NAME}' is ready.")
    print("\nAdd this to surfsense_backend/.env:")
    print(f"    DAYTONA_SNAPSHOT_ID={SNAPSHOT_NAME}")


if __name__ == "__main__":
    main()
