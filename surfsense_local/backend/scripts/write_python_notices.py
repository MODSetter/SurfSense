"""Write the Python third-party notices fragment for the desktop installer.

    uv run scripts/write_python_notices.py <fragments-dir>

Names come from `uv export --frozen --no-dev` for this platform; versions, ids
and texts from the installed distributions. `build:notices` in electron/ runs it.
"""

import argparse
import json
import os
import shutil
import subprocess
from importlib.metadata import distribution
from pathlib import Path

from notices.distribution_notice import python_notices
from notices.frozen_runtime import PYINSTALLER, PYINSTALLER_NOTE, interpreter_notice
from notices.shipped_requirements import shipped_names

BACKEND = Path(__file__).resolve().parents[1]


def exported_requirements() -> str:
    # `uv run` sets UV to its own path; PATH is the fallback.
    uv = os.environ.get("UV") or shutil.which("uv") or "uv"
    command = [uv, "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-project"]
    return subprocess.run(
        command, cwd=BACKEND, check=True, capture_output=True, text=True
    ).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fragments", type=Path)
    args = parser.parse_args()
    names = [*shipped_names(exported_requirements()), PYINSTALLER]
    entries = [
        interpreter_notice(),
        *python_notices(names, distribution, {PYINSTALLER: PYINSTALLER_NOTE}),
    ]
    args.fragments.mkdir(parents=True, exist_ok=True)
    out = args.fragments / "python.json"
    out.write_text(
        json.dumps({"entries": entries}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    bare = [e["name"] for e in entries if not e["text"]]
    print(f"{len(entries)} Python distributions in {out}")
    if bare:
        print(f"no licence text: {', '.join(bare)}")


if __name__ == "__main__":
    main()
