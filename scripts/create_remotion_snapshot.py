"""
One-time script to build and register the Remotion Daytona snapshot.

Run from the repo root:
    cd surfsense_backend
    uv run python ../scripts/create_remotion_snapshot.py

Prerequisites:
    - DAYTONA_API_KEY set in surfsense_backend/.env (or exported in shell)
    - DAYTONA_API_URL=https://app.daytona.io/api
    - DAYTONA_TARGET=us  (or eu)

After this script succeeds, add to surfsense_backend/.env:
    DAYTONA_REMOTION_SNAPSHOT_ID=remotion-surfsense
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from surfsense_backend (works whether you run from repo root or backend dir)
_here = Path(__file__).parent
for candidate in [_here / "../surfsense_backend/.env", _here / ".env"]:
    if candidate.exists():
        load_dotenv(candidate)
        break

from daytona import CreateSnapshotParams, Daytona, Image, Resources  # noqa: E402

SNAPSHOT_NAME = "remotion-surfsense"

# Linux shared library dependencies required by Chrome Headless Shell on Debian/Ubuntu.
# Source: https://remotion.dev/docs/miscellaneous/linux-dependencies
# Do NOT install the 'chromium' apt package — Remotion manages its own Chrome binary.
REMOTION_LINUX_DEPS = (
    "libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 "
    "libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 "
    "libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2"
)


def build_image() -> Image:
    """
    Declaratively build the Remotion sandbox image.

    Base image: node:22-bookworm-slim
      - Official Remotion Docker recommendation (https://remotion.dev/docs/docker)
      - Debian Bookworm (12) slim — smallest supported Debian with compatible glibc

    Layers (each cached independently by Daytona):
      1. Linux shared libraries required by Chrome Headless Shell
      2. Scaffold blank Remotion project + install npm packages
      3. Pre-download Chrome Headless Shell via 'npx remotion browser ensure'
         (Remotion manages its own pinned Chrome version, not the system one)
      4. Pre-create /out (render target) and /skills (agent skill files)
      5. Default command: sleep infinity (keeps container alive for agent tools)

    Note: ffmpeg is NOT installed separately — Remotion bundles its own ffmpeg
    binary since v4.0 inside @remotion/renderer.
    """
    return (
        Image.base("node:22-bookworm-slim")
        .run_commands(
            # Install only the shared libraries Chrome Headless Shell needs.
            # Do not install the 'chromium' package — that would conflict with
            # Remotion's own pinned Chrome Headless Shell.
            f"apt-get update && apt-get install -y {REMOTION_LINUX_DEPS}"
            " && rm -rf /var/lib/apt/lists/*",
        )
        .env({
            # Suppress interactive prompts from npm/npx
            "CI": "true",
        })
        .workdir("/remotion-project")
        .run_commands(
            # Scaffold a blank Remotion project (non-interactive, no browser open)
            "npx --yes create-video@latest . --blank --no-open",
            # Install all npm dependencies (remotion, @remotion/*, react, etc.)
            "npm install",
            # Pre-download Remotion's pinned Chrome Headless Shell into node_modules.
            # This runs at build time so sandboxes start immediately without downloading.
            # Source: https://remotion.dev/docs/miscellaneous/chrome-headless-shell
            "npx remotion browser ensure",
            # Pre-create directories the agent expects:
            #   /out    → where npx remotion render writes the MP4
            #   /skills → where SkillsMiddleware looks for SKILL.md rule files
            "mkdir -p /out /skills/remotion-best-practices",
        )
        .cmd(["sleep", "infinity"])
    )


def main() -> None:
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        print("ERROR: DAYTONA_API_KEY is not set.", file=sys.stderr)
        print("Add it to surfsense_backend/.env or export it in your shell.", file=sys.stderr)
        sys.exit(1)

    print(f"Building snapshot '{SNAPSHOT_NAME}' …")
    print("This takes 5–10 minutes (Chrome Headless Shell download included). Logs stream below:\n")

    daytona = Daytona()

    daytona.snapshot.create(
        CreateSnapshotParams(
            name=SNAPSHOT_NAME,
            image=build_image(),
            resources=Resources(
                cpu=2,      # 2 vCPU — Remotion renders frames in parallel
                memory=4,   # 4 GiB — Chrome Headless Shell + Node can use 2 GiB under load
                disk=8,     # 8 GiB — image + node_modules (~800 MB with Chrome) + MP4 output
            ),
        ),
        on_logs=lambda chunk: print(chunk, end="", flush=True),
    )

    print(f"\n\n✅  Snapshot '{SNAPSHOT_NAME}' is ready.")
    print("\nAdd this to surfsense_backend/.env:")
    print(f"    DAYTONA_REMOTION_SNAPSHOT_ID={SNAPSHOT_NAME}")


if __name__ == "__main__":
    main()
