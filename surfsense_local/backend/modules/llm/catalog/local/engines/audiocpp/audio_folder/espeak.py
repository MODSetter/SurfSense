"""Where a family that phonemises through eSpeak-ng finds the one the app ships.

audio.cpp's Kokoro reads the paths from the environment Electron gives the
server; Kitten reads only its session options, and without them looks for a
system eSpeak most computers do not have.
"""

from dataclasses import dataclass
from pathlib import Path

# The families that take eSpeak's paths only as session options.
_FROM_SESSION_OPTIONS = frozenset({"kitten_tts"})


@dataclass(frozen=True)
class Espeak:
    library: Path
    data: Path


def espeak_session_options(family: str, espeak: Espeak | None) -> dict[str, str]:
    if espeak is None or family not in _FROM_SESSION_OPTIONS:
        return {}
    return {
        f"{family}.espeak_library_path": espeak.library.as_posix(),
        f"{family}.espeak_data_path": espeak.data.as_posix(),
    }
