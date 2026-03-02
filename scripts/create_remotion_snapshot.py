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

# The Daytona sandbox runs as user 'daytona' with home /home/daytona.
# All project files and output must live under this path so they are
# accessible in the running sandbox (files placed outside /home/daytona
# during the Docker build are not visible to the daytona user session).
PROJECT_DIR = "/home/daytona/remotion-project"
OUT_DIR = "/home/daytona/out"
SKILLS_DIR = "/home/daytona/skills"
# Official @remotion/skills package — sparse-cloned during image build.
# Agent reads SKILL.md first (progressive disclosure), then individual rules files.
REMOTION_SKILLS_DIR = f"{SKILLS_DIR}/remotion-best-practices"
REMOTION_SKILLS_REPO = "https://github.com/remotion-dev/remotion.git"
REMOTION_SKILLS_REPO_PATH = "packages/skills/skills/remotion"

# NVM-managed node/npm/npx paths inside daytonaio/sandbox:0.6.0.
# These are stable paths regardless of which Node version NVM has active.
NPM = "/usr/local/share/nvm/current/bin/npm"
NPX = "/usr/local/share/nvm/current/bin/npx"

# Linux shared library dependencies required by Chrome Headless Shell.
# Source: https://remotion.dev/docs/miscellaneous/linux-dependencies
REMOTION_LINUX_DEPS = (
    "libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 "
    "libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 "
    "libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2"
)


def build_image() -> Image:
    """
    Declaratively build the Remotion sandbox image.

    Base image: daytonaio/sandbox:0.6.0
      - The Daytona runtime base. Sandboxes always run as user 'daytona'
        in /home/daytona — files placed outside that path during the Docker
        build are not accessible to the user session.
      - Already ships with git, NVM, Node.js, and Python.

    Layers (each cached independently by Daytona):
      1. Linux shared libraries required by Chrome Headless Shell
      2. Clone remotion-dev/template-helloworld into /home/daytona/remotion-project
      3. npm install (via NVM's npm)
      4. Pre-download Chrome Headless Shell (via NVM's npx)
      5. Sparse-clone official @remotion/skills into /home/daytona/skills/remotion-best-practices
      6. Pre-create output directory, set daytona ownership
    """
    return (
        Image.base("daytonaio/sandbox:0.6.0")
        .run_commands(
            # daytonaio/sandbox runs as a non-root user, so apt-get needs sudo.
            # Chrome Headless Shell needs these shared libs on Debian/Ubuntu.
            # Do NOT install 'chromium' — Remotion manages its own pinned Chrome.
            f"sudo apt-get update && sudo apt-get install -y {REMOTION_LINUX_DEPS}"
            " && sudo rm -rf /var/lib/apt/lists/*",
        )
        .env({"CI": "true"})
        .run_commands(
            # Clone the Hello World template into the daytona user's home.
            # We use Hello World (not blank) so the agent has working reference
            # code to read before overwriting it with the generated video.
            f"git clone --depth 1"
            f" https://github.com/remotion-dev/template-helloworld.git {PROJECT_DIR}",
            # Install npm dependencies using NVM's npm (already in the base image).
            f"cd {PROJECT_DIR} && {NPM} install",
            # Pre-download Remotion's pinned Chrome Headless Shell.
            f"cd {PROJECT_DIR} && {NPX} remotion browser ensure",
            # Sparse-clone just the @remotion/skills directory from the monorepo.
            # --filter=blob:none + --sparse avoids downloading the entire ~400 MB repo.
            f"mkdir -p {REMOTION_SKILLS_DIR} {OUT_DIR}"
            f" && git clone --depth 1 --filter=blob:none --sparse"
            f" {REMOTION_SKILLS_REPO} /tmp/remotion-skills"
            f" && cd /tmp/remotion-skills"
            f" && git sparse-checkout set {REMOTION_SKILLS_REPO_PATH}"
            f" && cp -r {REMOTION_SKILLS_REPO_PATH}/. {REMOTION_SKILLS_DIR}/"
            f" && rm -rf /tmp/remotion-skills",
            # Give the daytona user ownership of everything we just created.
            f"chown -R daytona:daytona {PROJECT_DIR} {OUT_DIR} {SKILLS_DIR}",
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
