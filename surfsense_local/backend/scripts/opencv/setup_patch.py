"""Let opencv-python's setup.py package a build without videoio or typing stubs.

setup.py fails unless the build made the Windows FFmpeg plugin and the generated
`cv2.typing` module. Without videoio there is no plugin, and upstream's stub
generator gives up (a warning) at the first features, calib or dnn symbol a
smaller build lacks, so no `.pyi` stubs, `py.typed` or `cv2.typing`: annotation
helpers that neither the app nor its libraries import.
"""

from pathlib import Path

_EDITS = (
    (
        '            [r"bin/opencv_videoio_ffmpeg\\d{3}%s\\.dll" % ("_64" if is64 else "")]\n',
        "            []\n",
    ),
    (
        '        [ r"python/cv2/py.typed" ] if sys.version_info >= (3, 6) else []\n',
        "        [] if sys.version_info >= (3, 6) else []\n",
    ),
    (
        '        rearrange_cmake_output_data["cv2.typing"] = ["python/cv2" + r"/typing/.*\\.py"]\n',
        "        pass\n",
    ),
)


def without_ffmpeg_or_stubs(source: Path) -> None:
    path = source / "setup.py"
    text = path.read_text(encoding="utf-8")
    for before, after in _EDITS:
        if text.count(before) != 1:
            raise SystemExit(f"setup.py changed upstream; review {Path(__file__).name}")
        text = text.replace(before, after)
    path.write_text(text, encoding="utf-8")
