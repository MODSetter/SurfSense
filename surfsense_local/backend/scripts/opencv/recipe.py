"""The build switches for the app's minimal cv2: the one place local and CI builds read.

Everything not named here stays as opencv-python's own wheels build it: IPP,
OpenCL, ITT, the CPU baseline and dispatch, and KleidiCV and carotene on Apple
silicon, so every call the app makes returns what PyPI's wheel returns.
"""

import os
import sys

# The app's calls reach core, imgproc, imgcodecs and geometry, which holds
# getPerspectiveTransform, minAreaRect and boxPoints in 5.0 and needs flann.
MODULES = ("core", "flann", "geometry", "imgproc", "imgcodecs", "python3")

_EVERYWHERE = {
    "BUILD_LIST": ",".join(MODULES),
    # setup.py finds the abi3 module only when CMAKE_ARGS carries this exact text.
    "PYTHON3_LIMITED_API": "ON",
    "WITH_FFMPEG": "OFF",
    # Docling encodes PNG and RapidOCR's debug writer may ask for JPEG, from the
    # sources the sdist pins. Upstream's Linux wheel carries libpng 1.6.58
    # instead, whose only change from the pinned 1.6.57 is in reading.
    "BUILD_PNG": "ON",
    "BUILD_JPEG": "ON",
    # libjpeg-turbo's own switch: fail rather than build without SIMD, as
    # upstream never does (x86 needs NASM).
    "REQUIRE_SIMD": "ON",
    "WITH_TIFF": "OFF",
    "WITH_WEBP": "OFF",
    "WITH_OPENJPEG": "OFF",
    "WITH_JASPER": "OFF",
    "WITH_OPENEXR": "OFF",
    "WITH_AVIF": "OFF",
    # Only dnn reads them.
    "WITH_PROTOBUF": "OFF",
    "WITH_FLATBUFFERS": "OFF",
    # Off in every upstream wheel; a runner that has Eigen must not turn it on.
    "WITH_EIGEN": "OFF",
}

_PER_PLATFORM = {
    # zlib as upstream's wheels take it, so PNG's deflate is the same code:
    # built from the sdist on Windows and macOS, the system's libz.so.1 on Linux.
    "win32": {"BUILD_ZLIB": "ON"},
    "darwin": {"BUILD_ZLIB": "ON"},
    "linux": {
        "BUILD_ZLIB": "OFF",
        # 5.0 requires LAPACK, and upstream's Linux wheel links OpenBLAS (39 MB).
        # No kept call reaches it: OpenCV solves matrices under 25 rows itself.
        "BUILD_CLAPACK": "ON",
    },
}

# Upstream's wheel targets 13.0; the app's floor is 13.3.
MACOS_DEPLOYMENT_TARGET = "13.0"


def cmake_args() -> str:
    switches = {**_EVERYWHERE, **_PER_PLATFORM.get(sys.platform, {})}
    return " ".join(f"-D{name}={value}" for name, value in switches.items())


def environment() -> dict[str, str]:
    """What setup.py reads, beside the caller's own environment."""
    env = {
        "ENABLE_HEADLESS": "1",
        # As upstream's CI: Visual Studio's generator on Windows, Makefiles elsewhere.
        "CI_BUILD": "1",
        "CMAKE_ARGS": cmake_args(),
        # The name upstream's metadata carries, which the licence notices print;
        # setuptools 69 would keep setup.py's underscores.
        "OPENCV_PYTHON_PACKAGE_NAME": "opencv-python-headless",
    }
    if sys.platform == "win32":
        # No CMAKE_BUILD_PARALLEL_LEVEL: MSVC compiles each project's files in
        # parallel already (/MP), and more projects at once ran 16 GB out of
        # memory (C1356). Reused MSBuild nodes would hold the tree open after.
        env["MSBUILDDISABLENODEREUSE"] = "1"
    else:
        env["CMAKE_BUILD_PARALLEL_LEVEL"] = str(os.cpu_count() or 2)
    if sys.platform == "darwin":
        env["MACOSX_DEPLOYMENT_TARGET"] = MACOS_DEPLOYMENT_TARGET
    return env
