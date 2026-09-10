"""Download Docling layout, table, and OCR weights for packaging.

`uv run scripts/fetch_docling_models.py` places them where ingest reads them
in development; pass a models root (`... models`) to stage them for an
installer, which electron-builder copies into resources/models.
"""

import logging
import sys
from pathlib import Path

from worker.ingestion.parser_pack import (
    PARSER_DIR_NAME,
    missing_parser_folders,
    parser_dir,
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


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    into = Path(sys.argv[1]) / PARSER_DIR_NAME if len(sys.argv) > 1 else parser_dir()
    if not missing_parser_folders(into.parent):
        print(f"have {into}")
        return 0
    fetch(into)
    still = missing_parser_folders(into.parent)
    if still:
        print(f"missing after fetch: {', '.join(still)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
