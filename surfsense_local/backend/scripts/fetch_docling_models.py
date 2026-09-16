"""Download Docling layout, table, and OCR weights for packaging.

`uv run scripts/fetch_docling_models.py` places them where ingest reads them
in development; pass a models root (`... models`) to stage them for an
installer, which electron-builder copies into resources/models.
"""

import logging
import shutil
import sys
from pathlib import Path

from worker.ingestion.parser_pack import (
    PARSER_DIR_NAME,
    missing_parser_folders,
    parser_dir,
)

# download_models fetches every engine variant of the layout model and the whole
# tableformer repo, but parsing.py leaves both at their defaults -- the
# Transformers layout engine and TableFormerMode.ACCURATE -- so neither of these
# is ever opened. Together they are 302 MB of the installer.
UNUSED = (
    "docling-project--docling-layout-heron-onnx",
    "docling-project--docling-models/model_artifacts/tableformer/fast",
)


def fetch(into: Path) -> None:
    # Official Docling prefetch: same folders ingest expects under artifacts_path.
    from docling.utils.model_downloader import download_models

    download_models(
        output_dir=into,
        progress=True,
        with_layout=True,
        with_tableformer=True,
        with_rapidocr=True,
        rapidocr_models=["onnxruntime:ch"],
        with_code_formula=False,
        with_picture_classifier=False,
    )


def prune(into: Path) -> None:
    """Drop the prefetched weights ingest never loads."""
    for relative in UNUSED:
        target = into.joinpath(*relative.split("/"))
        if target.is_dir():
            shutil.rmtree(target)
            print(f"pruned {relative}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    into = Path(sys.argv[1]) / PARSER_DIR_NAME if len(sys.argv) > 1 else parser_dir()
    if not missing_parser_folders(into.parent):
        # Prune here too: a tree from an earlier build still carries them.
        prune(into)
        print(f"have {into}")
        return 0
    fetch(into)
    still = missing_parser_folders(into.parent)
    if still:
        print(f"missing after fetch: {', '.join(still)}", file=sys.stderr)
        return 1
    prune(into)
    return 0


if __name__ == "__main__":
    sys.exit(main())
