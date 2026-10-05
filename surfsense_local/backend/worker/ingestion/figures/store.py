"""Figures written beside a source's original; keeping them never fails an ingest."""

import logging
import shutil
from pathlib import Path
from typing import Any

from modules.documents.source_figures.layout import (
    can_hold_figures,
    figure_png,
    figures_dir,
    write_index,
)
from worker.ingestion.figures.pictures import pictures_in

logger = logging.getLogger(__name__)

MESSAGE_CHARS = 500


def keep_figures(original: Path, converted: Any) -> None:
    """Replace the source's figures with the pictures in `converted`, Docling's reading."""
    if not can_hold_figures(original):
        return
    folder = figures_dir(original.parent)
    try:
        _empty(folder)
        entries = []
        for n, picture in enumerate(pictures_in(original, converted), start=1):
            picture.image.save(figure_png(folder, n), "PNG")
            entries.append(
                {
                    "n": n,
                    "caption": picture.caption,
                    "page": picture.page,
                    "width": picture.image.width,
                    "height": picture.image.height,
                }
            )
        write_index(folder, entries, error=None)
    except Exception as failure:  # the text is what ingest is for; figures are extra
        record_figures_failure(original, failure)


def record_figures_failure(original: Path, failure: Exception) -> None:
    """Index no figures and say why, so nobody queues the same failure again."""
    logger.warning("could not keep the figures of %s", original, exc_info=failure)
    folder = figures_dir(original.parent)
    try:
        _empty(folder)
        write_index(
            folder, [], error=f"{type(failure).__name__}: {failure}"[:MESSAGE_CHARS]
        )
    except OSError:
        logger.exception("could not record the figures failure of %s", original)


def _empty(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
    # Not parents: a source deleted meanwhile must not get its folder back.
    folder.mkdir()
