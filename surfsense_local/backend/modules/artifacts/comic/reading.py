"""How a bound comic reads: page by page or as one scroll, left to right or right to left."""

from typing import Literal

Layout = Literal["pages", "scroll"]
Direction = Literal["ltr", "rtl"]
LAYOUTS: tuple[Layout, ...] = ("pages", "scroll")
DIRECTIONS: tuple[Direction, ...] = ("ltr", "rtl")
