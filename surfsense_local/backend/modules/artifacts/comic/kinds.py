"""Each kind of comic: how it reads, how its pictures are shaped and bound, and how it looks.

The agent's skill (`surfsense-pictures/comics.md`) states the same table for the agent.
"""

from dataclasses import dataclass
from typing import Literal

Shape = Literal["portrait", "landscape"]


@dataclass(frozen=True)
class Kind:
    key: str
    name: str
    # What one picture is, as a page prompt says it.
    picture: str
    unit: str
    shape: Shape
    layout: Literal["pages", "scroll"]
    direction: Literal["ltr", "rtl"]
    looks: str
    default_pages: int
    # False for a picture book or a storyboard: its text is never in the picture.
    bubbles: bool = True


KINDS: dict[str, Kind] = {
    kind.key: kind
    for kind in (
        Kind(
            "western",
            "Western comic",
            "A portrait comic page of 4 to 6 black-bordered panels",
            "Page",
            "portrait",
            "pages",
            "ltr",
            "Full-colour comic book art, clean bold ink lines, flat colours, white "
            "gutters, caption boxes, speech bubbles with clear hand-lettered capitals.",
            4,
        ),
        Kind(
            "graphic_novel",
            "Graphic novel",
            "A portrait graphic novel page of 3 to 6 panels, with room for quiet, "
            "wordless panels",
            "Page",
            "portrait",
            "pages",
            "ltr",
            "Full-colour graphic novel art, confident ink lines, cinematic framing.",
            4,
        ),
        Kind(
            "bande_dessinee",
            "Bande dessinée",
            "A detailed portrait album page of 6 to 9 smaller panels",
            "Page",
            "portrait",
            "pages",
            "ltr",
            "Franco-Belgian bande dessinée, clean 'ligne claire' lines, flat colour, "
            "detailed backgrounds.",
            4,
        ),
        Kind(
            "manga",
            "Manga",
            "A portrait manga page of 3 to 6 panels, read right to left: panel 1 top "
            "right, the last bottom left; its bubbles read right to left too",
            "Page",
            "portrait",
            "pages",
            "rtl",
            "Black-and-white manga with screentone, speed lines and expressive faces.",
            4,
        ),
        Kind(
            "manhua",
            "Manhua",
            "A portrait manhua page of 3 to 6 panels",
            "Page",
            "portrait",
            "pages",
            "ltr",
            "Full-colour, painterly manhua art.",
            4,
        ),
        Kind(
            "webtoon",
            "Webtoon",
            "One tall webtoon panel, one beat of the story, nothing else in the picture",
            "Beat",
            "portrait",
            "scroll",
            "ltr",
            "Full-colour webtoon art, soft shading, clean digital lines.",
            8,
        ),
        Kind(
            "comic_strip",
            "Comic strip",
            "One landscape comic strip of 3 or 4 panels in a row, the punchline in the "
            "last",
            "Strip",
            "landscape",
            "pages",
            "ltr",
            "Newspaper comic strip, simple shapes, bold outlines, flat colour.",
            1,
        ),
        Kind(
            "yonkoma",
            "Yonkoma (4-koma)",
            "One portrait yonkoma of 4 equal panels stacked top to bottom: setup, "
            "development, turn, punchline",
            "Strip",
            "portrait",
            "pages",
            "ltr",
            "Manga-style 4-koma strip, black and white, simple expressive faces.",
            1,
        ),
        Kind(
            "picture_book",
            "Picture book",
            "One full-page illustration of one moment, no speech bubbles",
            "Page",
            "portrait",
            "pages",
            "ltr",
            "Children's picture book illustration, soft colour, gentle shapes.",
            4,
            bubbles=False,
        ),
        Kind(
            "storyboard",
            "Storyboard",
            "One landscape storyboard frame of one shot",
            "Shot",
            "landscape",
            "pages",
            "ltr",
            "Rough, sketchy storyboard frame, grey pencil tones, arrows for camera "
            "and movement.",
            6,
            bubbles=False,
        ),
    )
}

DEFAULT_KIND = "western"
# Each picture is billed or takes minutes, so a comic stops here.
MAX_PAGES = 12
