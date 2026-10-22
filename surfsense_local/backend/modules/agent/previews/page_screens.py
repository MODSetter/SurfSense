"""A web page's capture cut into screens, top to bottom, as a document is into pages."""

from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from modules.agent.previews.page_images import PAGE_LIMIT

# Electron captures at this width; a screen is about what a laptop shows of it.
SCREEN_HEIGHT_PX = 1000


class UnreadableCaptureError(ValueError):
    """The capture is no image Pillow will open."""


def cut_into_screens(png: bytes, folder: Path) -> list[Path]:
    """Write up to PAGE_LIMIT screens as page-<n>.png, replacing a version's old ones."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("page-*.png"):
        old.unlink()
    # Electron sends at most PAGE_LIMIT screens; Pillow refuses a far larger bomb itself.
    try:
        capture = Image.open(BytesIO(png))
        capture.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
        raise UnreadableCaptureError(str(error)) from error
    with capture:
        screens: list[Path] = []
        for number in range(1, PAGE_LIMIT + 1):
            top = (number - 1) * SCREEN_HEIGHT_PX
            if top >= capture.height:
                break
            bottom = min(capture.height, top + SCREEN_HEIGHT_PX)
            path = folder / f"page-{number}.png"
            capture.crop((0, top, capture.width, bottom)).save(path, format="PNG")
            screens.append(path)
    return screens
