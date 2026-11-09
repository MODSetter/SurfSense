"""Build opencv-python-headless with only the modules the app calls.

    python scripts/opencv/build_wheel.py <work-dir>

Builds the sdist uv.lock pins with recipe.py's switches, the way upstream's CI
does (`setup.py bdist_wheel --py-limited-api=cp37`), into <work-dir>/dist. Needs
CMake, and Visual Studio 2022 on Windows, Xcode's tools on macOS, or on Linux
the manylinux_2_28 image upstream's wheel is built in.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import tarfile
import time
import urllib.request
import venv
from pathlib import Path

from pins import BUILD_TOOLS, Sdist, locked_sdist
from recipe import environment
from setup_patch import without_ffmpeg_or_stubs


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetched(sdist: Sdist, folder: Path) -> Path:
    archive = folder / sdist.url.rsplit("/", 1)[-1]
    if not archive.is_file() or _sha256(archive) != sdist.sha256:
        folder.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(sdist.url, archive)
    if (digest := _sha256(archive)) != sdist.sha256:
        raise SystemExit(
            f"{archive.name} hashes to {digest}; uv.lock pins {sdist.sha256}"
        )
    return archive


def unpacked(archive: Path, folder: Path) -> Path:
    """The sdist's tree at <folder>; a short name, since MSBuild's paths under it are long."""
    staging = folder.parent / "unpacking"
    for stale in (folder, staging):
        if stale.exists():
            shutil.rmtree(stale)
    with tarfile.open(archive) as tar:
        tar.extractall(staging, filter="data")
    # Today's times, not July's: Windows' Storage Sense deletes old files under
    # %TEMP%, and took a build's sources mid-build.
    now = time.time()
    for root, _, files in os.walk(staging):
        for name in files:
            os.utime(os.path.join(root, name), (now, now))
    (tree,) = staging.iterdir()
    tree.rename(folder)
    staging.rmdir()
    return folder


def build_python(folder: Path) -> Path:
    venv.create(folder, with_pip=True, clear=True)
    python = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = [python, "-m", "pip", "install", "--disable-pip-version-check"]
    subprocess.run([*install, *BUILD_TOOLS], check=True)
    return python


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("work", type=Path)
    # Not resolve(): that would undo a `subst` drive kept short for MSBuild.
    work = parser.parse_args().work.absolute()
    source = unpacked(fetched(locked_sdist(), work / "sdist"), work / "s")
    without_ffmpeg_or_stubs(source)
    python = build_python(work / "build-venv")
    dist = work / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    command = [python, "setup.py", "bdist_wheel", "--py-limited-api=cp37"]
    subprocess.run(
        [*command, f"--dist-dir={dist}"],
        cwd=source,
        env={**os.environ, **environment()},
        check=True,
    )
    (wheel,) = dist.glob("*.whl")
    print(f"{wheel}: {wheel.stat().st_size:,} B")


if __name__ == "__main__":
    main()
