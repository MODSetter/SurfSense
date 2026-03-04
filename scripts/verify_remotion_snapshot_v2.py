"""
Verify the V2 Remotion snapshot works end-to-end.

Run from repo root:
    cd surfsense_backend
    uv run python ../scripts/verify_remotion_snapshot_v2.py

Checks:
    1. tsc --noEmit passes
    2. npx remotion render produces a real MP4
    3. Chrome Headless Shell pre-downloaded
    4. V2 packages installed (remotion-bits, lucide-react, @remotion/paths, etc.)
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).parent
for candidate in [_here / "../surfsense_backend/.env", _here / ".env"]:
    if candidate.exists():
        load_dotenv(candidate)
        break

from daytona import CreateSandboxFromSnapshotParams, Daytona  # noqa: E402

SNAPSHOT_NAME = os.environ.get("DAYTONA_REMOTION_SNAPSHOT_ID", "remotion-surfsense-v2")

V2_PACKAGES = [
    "remotion-bits",
    "culori",
    "lucide-react",
    "@remotion/paths",
    "@remotion/shapes",
    "@remotion/layout-utils",
    "@remotion/animation-utils",
    "@remotion/google-fonts",
]


def check(label: str, result) -> bool:
    ok = result.exit_code == 0
    status = "✅" if ok else "❌"
    print(f"\n{status}  {label}")
    if result.result:
        for line in result.result.strip().splitlines()[-5:]:
            print(f"    {line}")
    return ok


def main() -> None:
    print(f"Creating test sandbox from snapshot '{SNAPSHOT_NAME}' …")
    daytona = Daytona()
    sandbox = daytona.create(CreateSandboxFromSnapshotParams(snapshot=SNAPSHOT_NAME))
    print(f"Sandbox ready: {sandbox.id}\n")

    passed = True

    try:
        PROJECT = "/home/daytona/remotion-project"
        OUT     = "/home/daytona/out"
        NPX     = "/usr/local/share/nvm/current/bin/npx"

        # 1 — TypeScript check
        passed &= check(
            "tsc --noEmit",
            sandbox.process.exec(f"cd {PROJECT} && {NPX} tsc --noEmit 2>&1"),
        )

        # 2 — Render a test MP4
        passed &= check(
            "npx remotion render HelloWorld",
            sandbox.process.exec(
                f"cd {PROJECT} && {NPX} remotion render HelloWorld {OUT}/test.mp4 2>&1",
                timeout=120,
            ),
        )

        # 3 — Confirm the MP4 file was produced
        passed &= check(
            "MP4 file exists",
            sandbox.process.exec(f"ls -lh {OUT}/test.mp4"),
        )

        # 4 — Chrome Headless Shell is pre-downloaded
        passed &= check(
            "Chrome Headless Shell exists",
            sandbox.process.exec(
                f"ls {PROJECT}/node_modules/.remotion/chrome-headless-shell/"
            ),
        )

        # 5 — V2 packages installed
        for pkg in V2_PACKAGES:
            pkg_dir = pkg if not pkg.startswith("@") else pkg
            passed &= check(
                f"npm package: {pkg}",
                sandbox.process.exec(
                    f"ls {PROJECT}/node_modules/{pkg_dir}/package.json"
                ),
            )

    finally:
        print("\nCleaning up test sandbox …")
        sandbox.delete()

    print()
    if passed:
        print("✅  All checks passed. The V2 snapshot is ready for the video agent.")
        print(f"\nMake sure surfsense_backend/.env contains:")
        print(f"    DAYTONA_REMOTION_SNAPSHOT_ID={SNAPSHOT_NAME}")
    else:
        print("❌  Some checks failed. Fix the issues and re-run create_remotion_snapshot_v2.py.")
        sys.exit(1)


if __name__ == "__main__":
    main()
