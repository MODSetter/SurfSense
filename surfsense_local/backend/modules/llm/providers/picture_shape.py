"""A picture's proportions, as each kind of image endpoint asks for them."""

from typing import Literal

Shape = Literal["square", "portrait", "landscape"]
SHAPES: tuple[Shape, ...] = ("square", "portrait", "landscape")

# The sizes OpenAI's image models take; other servers round to their own.
SIZE: dict[Shape, str] = {
    "square": "1024x1024",
    "portrait": "1024x1536",
    "landscape": "1536x1024",
}
ASPECT_RATIO: dict[Shape, str] = {
    "square": "1:1",
    "portrait": "2:3",
    "landscape": "3:2",
}
_RATIO: dict[Shape, tuple[int, int]] = {
    "square": (1, 1),
    "portrait": (2, 3),
    "landscape": (3, 2),
}


def local_dimensions(shape: Shape, pixels: int) -> tuple[int, int]:
    """About `pixels` in all, at the shape's ratio, each side a multiple of 64 as sd.cpp needs."""
    across, down = _RATIO[shape]
    unit = (pixels / (across * down)) ** 0.5
    return _to_64(across * unit), _to_64(down * unit)


def _to_64(side: float) -> int:
    return max(64, round(side / 64) * 64)


def shape_of(width: int, height: int) -> Shape:
    """The nearest shape to a picture's own proportions, so a redraw keeps them."""
    ratio = width / height
    if ratio > 1.2:
        return "landscape"
    if ratio < 1 / 1.2:
        return "portrait"
    return "square"
