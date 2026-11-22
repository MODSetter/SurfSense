"""What the minimal cv2 is built from: the sdist uv.lock resolves, and the build tools.

    python scripts/opencv/pins.py

prints `version=`, `sha256=` and `linux_image=` lines for the workflow.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
DISTRIBUTION = "opencv-python-headless"

# opencv-python's pyproject asks for these loosely; pinned so a cached wheel and a
# fresh one build alike. numpy 2.0.2 is what upstream builds Python 3.12 against;
# wheel stays below 0.46, which hands bdist_wheel to setuptools 70.1+. distro is
# scikit-build's own dependency. pip is pinned too: the Linux image's Python carries
# pip 25.0.1 and uv's Python pip 26.2.2, which the Windows and macOS builds used.
BUILD_TOOLS = (
    "numpy==2.0.2",
    "scikit-build==0.19.1",
    "setuptools==69.5.1",
    "wheel==0.45.1",
    "packaging==26.3",
    "distro==1.9.0",
    "pip==26.2.2",
)

# The image upstream built 5.0.0.93's Linux wheel in (the sdist's
# docker/manylinux_2_28/Dockerfile_x86_64 names version 20260531): the compiler
# that built PyPI's wheel, gcc-toolset-14, and glibc 2.28.
LINUX_IMAGE = (
    "quay.io/opencv-ci/opencv-python-manylinux_2_28-x86-64:20260531"
    "@sha256:26c8159d923fbaa3c893aa53cdf67d5b2da7f858daf388a494a282ca118b83c9"
)


@dataclass(frozen=True)
class Sdist:
    version: str
    url: str
    sha256: str


def locked_sdist() -> Sdist:
    """The sdist of the version the backend resolves, so the wheel replaces it exactly."""
    lock = tomllib.loads((BACKEND / "uv.lock").read_text(encoding="utf-8"))
    (package,) = [p for p in lock["package"] if p["name"] == DISTRIBUTION]
    algorithm, digest = package["sdist"]["hash"].split(":", 1)
    if algorithm != "sha256":
        raise SystemExit(f"uv.lock hashes {DISTRIBUTION}'s sdist with {algorithm}")
    return Sdist(package["version"], package["sdist"]["url"], digest)


if __name__ == "__main__":
    sdist = locked_sdist()
    print(f"version={sdist.version}")
    print(f"sha256={sdist.sha256}")
    print(f"linux_image={LINUX_IMAGE}")
