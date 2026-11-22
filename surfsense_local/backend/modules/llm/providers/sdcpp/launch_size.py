"""The pixel count a local model is launched to draw, from its `-W` and `-H`."""

from collections.abc import Sequence
from itertools import pairwise

from modules.llm.providers.sdcpp.generator import DEFAULT_PIXELS


def launch_pixels(args: Sequence[str]) -> int:
    """Its reviewed size, kept when a shape changes the proportions."""
    width, height = _flag(args, "-W"), _flag(args, "-H")
    if width is None or height is None:
        return DEFAULT_PIXELS
    return width * height


def _flag(args: Sequence[str], name: str) -> int | None:
    for flag, value in pairwise(args):
        if flag == name and value.isdigit():
            return int(value)
    return None
