"""
One-time script to build and register the Remotion Daytona snapshot (V2).

Extends V1 by installing additional npm packages required by prompts_v2:
  remotion-bits, culori, lucide-react,
  @remotion/paths, @remotion/shapes,
  @remotion/layout-utils, @remotion/animation-utils

Run from the repo root:
    cd surfsense_backend
    uv run python ../scripts/create_remotion_snapshot_v2.py

Prerequisites:
    - DAYTONA_API_KEY set in surfsense_backend/.env (or exported in shell)
    - DAYTONA_API_URL=https://app.daytona.io/api
    - DAYTONA_TARGET=us  (or eu)

After this script succeeds, add to surfsense_backend/.env:
    DAYTONA_REMOTION_SNAPSHOT_ID=remotion-surfsense-v2
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).parent
for candidate in [_here / "../surfsense_backend/.env", _here / ".env"]:
    if candidate.exists():
        load_dotenv(candidate)
        break

from daytona import CreateSnapshotParams, Daytona, Image, Resources  # noqa: E402

SNAPSHOT_NAME = "remotion-surfsense-v2"
OLD_SNAPSHOT_NAME = "remotion-surfsense"

PROJECT_DIR = "/home/daytona/remotion-project"
OUT_DIR = "/home/daytona/out"

NPM = "/usr/local/share/nvm/current/bin/npm"
NPX = "/usr/local/share/nvm/current/bin/npx"

REMOTION_LINUX_DEPS = (
    "libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 "
    "libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 "
    "libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2"
)

V2_PACKAGES = (
    "remotion-bits"
    " culori"
    " lucide-react"
    " @remotion/paths"
    " @remotion/shapes"
    " @remotion/layout-utils"
    " @remotion/animation-utils"
    " @remotion/google-fonts"
)


def build_image() -> Image:
    """
    Build the V2 Remotion sandbox image.

    Layers:
      1. Linux shared libraries required by Chrome Headless Shell
      2. Clone remotion template into /home/daytona/remotion-project
      3. npm install (base + V2 packages)
      4. Pre-download Chrome Headless Shell
      5. Create output directory, set ownership

    Skills are NOT included — they live in the backend repo at
    surfsense_backend/app/agents/video/skills/ and are loaded by the
    pipeline into the system prompt at runtime.
    """
    return (
        Image.base("daytonaio/sandbox:0.6.0")
        .run_commands(
            f"sudo apt-get update && sudo apt-get install -y {REMOTION_LINUX_DEPS}"
            " && sudo rm -rf /var/lib/apt/lists/*",
        )
        .env({"CI": "true"})
        .run_commands(
            f"git clone --depth 1"
            f" https://github.com/remotion-dev/template-helloworld.git {PROJECT_DIR}",
            f"cd {PROJECT_DIR} && {NPM} install",
            f"cd {PROJECT_DIR} && {NPM} install {V2_PACKAGES}",
            f"cd {PROJECT_DIR} && {NPX} remotion browser ensure",
            f"mkdir -p {OUT_DIR}",
            f"chown -R daytona:daytona {PROJECT_DIR} {OUT_DIR}",
        )
        .cmd(["sleep", "infinity"])
    )


def main() -> None:
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        print("ERROR: DAYTONA_API_KEY is not set.", file=sys.stderr)
        print("Add it to surfsense_backend/.env or export it in your shell.", file=sys.stderr)
        sys.exit(1)

    daytona = Daytona()

    for name in [OLD_SNAPSHOT_NAME, SNAPSHOT_NAME]:
        try:
            old = daytona.snapshot.get(name)
            print(f"Deleting existing snapshot '{name}' …")
            daytona.snapshot.delete(old)
            print(f"Deleted '{name}'. Waiting for removal to propagate …")
            for attempt in range(30):
                time.sleep(2)
                try:
                    daytona.snapshot.get(name)
                except Exception:
                    print(f"Confirmed '{name}' is gone.\n")
                    break
            else:
                print(f"WARNING: '{name}' may still exist after 60s. Proceeding anyway.\n")
        except Exception:
            pass

    print(f"Building snapshot '{SNAPSHOT_NAME}' …")
    print("This takes 5–10 minutes (Chrome Headless Shell download included). Logs stream below:\n")

    daytona.snapshot.create(
        CreateSnapshotParams(
            name=SNAPSHOT_NAME,
            image=build_image(),
            resources=Resources(
                cpu=2,
                memory=4,
                disk=8,
            ),
        ),
        on_logs=lambda chunk: print(chunk, end="", flush=True),
    )

    print(f"\n\n✅  Snapshot '{SNAPSHOT_NAME}' is ready.")
    print("\nAdd this to surfsense_backend/.env:")
    print(f"    DAYTONA_REMOTION_SNAPSHOT_ID={SNAPSHOT_NAME}")


if __name__ == "__main__":
    main()
