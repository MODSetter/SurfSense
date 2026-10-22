"""Check the minimal cv2 answers every call the app makes exactly as PyPI's wheel does.

    python scripts/opencv/check_same_outputs.py <dist-dir> <work-dir>

Makes two venvs with numpy, Pillow, RapidOCR and onnxruntime at the backend's
locked versions, one with PyPI's opencv-python-headless and one with the wheel,
runs record_calls.py in each and compare_outputs.py over both. Needs uv.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pins import BACKEND, DISTRIBUTION

HERE = Path(__file__).resolve().parent
PACKAGES = ("numpy", "pillow", "rapidocr", "onnxruntime")
UV = os.environ.get("UV") or shutil.which("uv") or "uv"
PINNED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==")


def locked_constraints(work: Path) -> tuple[Path, Path]:
    export = subprocess.run(
        [UV, "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-project"],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    # Only `name==version` lines: a constraint cannot name a local path.
    pinned = [line for line in export.splitlines() if PINNED.match(line)]
    constraints = work / "constraints.txt"
    constraints.write_text("\n".join(pinned) + "\n", encoding="utf-8")
    # RapidOCR asks for the GUI wheel; the backend drops it the same way.
    excludes = work / "excludes.txt"
    excludes.write_text("opencv-python\n", encoding="utf-8")
    return constraints, excludes


def environment(folder: Path, cv2: str, constraints: Path, excludes: Path) -> Path:
    subprocess.run([UV, "venv", "--python", "3.12", str(folder)], check=True)
    python = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = [UV, "pip", "install", "--python", str(python), "-c", str(constraints)]
    subprocess.run([*install, "--excludes", str(excludes), *PACKAGES, cv2], check=True)
    return python


def modules(python: Path) -> str:
    probe = "import cv2, re; print(re.search(r'To be built:\\s*(.*)', cv2.getBuildInformation())[1])"
    return subprocess.run(
        [str(python), "-I", "-c", probe], check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "dist", type=Path, help="the folder build_wheel.py wrote the wheel to"
    )
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    (wheel,) = args.dist.absolute().glob("*.whl")
    work = args.work.absolute()
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    constraints, excludes = locked_constraints(work)
    runs = {
        "pypi": environment(work / "pypi", DISTRIBUTION, constraints, excludes),
        "minimal": environment(work / "minimal", str(wheel), constraints, excludes),
    }
    for label, python in runs.items():
        print(f"{label}: cv2 modules {modules(python)}", flush=True)
        record = [
            str(python),
            "-I",
            str(HERE / "record_calls.py"),
            str(work / f"{label}.npz"),
        ]
        subprocess.run(record, check=True)
    compare = [str(runs["pypi"]), "-I", str(HERE / "compare_outputs.py")]
    result = subprocess.run(
        [*compare, str(work / "pypi.npz"), str(work / "minimal.npz")]
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
