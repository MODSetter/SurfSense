"""Whether a path in a thread's folder fits Windows without long paths, measured as Windows measures it.

Windows counts UTF-16 units, so a character outside the BMP (an emoji) counts two.
"""

from pathlib import Path

# MAX_PATH less its terminator; CreateDirectory leaves 12 more for an 8.3 name.
LONGEST_PATH = 259
LONGEST_DIRECTORY = 247

TOO_DEEP = (
    "SurfSense's data folder is too deep on this computer for this chat to hold {what}."
)


def units(text: str) -> int:
    """The length Windows counts: UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def cut(text: str, room: int) -> str:
    """As much of the start of `text` as fits in `room` units, never half a character."""
    taken = 0
    for index, character in enumerate(text):
        taken += units(character)
        if taken > room:
            return text[:index]
    return text


def fits(path: Path) -> bool:
    """Whether the file and the folder it goes in can both be made."""
    return (
        units(str(path)) <= LONGEST_PATH
        and units(str(path.parent)) <= LONGEST_DIRECTORY
    )
