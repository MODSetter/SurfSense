"""The worker's command line: a queue to drain, or one of the self-run modes."""

import sys


def check_vision_runtime() -> None:
    """Fail fast when a frozen worker dropped Docling's lazy vision imports."""
    import torchvision
    from transformers import AutoImageProcessor

    sys.stdout.write(
        f"vision imports OK ({AutoImageProcessor.__name__}, "
        f"torchvision {torchvision.__version__})\n"
    )


def run(arguments: list[str]) -> None:
    if arguments == ["--check-vision-runtime"]:
        check_vision_runtime()
    elif arguments == ["--check-scan-ocr"]:
        from worker.ingestion.scan_ocr.check import check_scan_ocr

        sys.stdout.write(check_scan_ocr() + "\n")
    elif len(arguments) == 3 and arguments[0] == "--check-docling-reading":
        # For the release build: layout, TableFormer and OCR run for real, so a
        # trimmed bundle is compared with source on what Docling reads.
        from pathlib import Path

        from worker.ingestion.parsing import convert

        markdown = convert(Path(arguments[1])).export_to_markdown()
        Path(arguments[2]).write_text(markdown, encoding="utf-8")
    elif len(arguments) == 2 and arguments[0] == "--run-document-script":
        # Ahead of the consumer's imports: a script process loads no queue,
        # database or settings.
        from worker.document_script.child import main

        main(arguments[1])
    elif len(arguments) == 3 and arguments[0] == "--decode-audio":
        # Ahead of the consumer's imports too: a decode needs only miniaudio.
        from worker.audio_decode.child import main

        main(arguments[1], arguments[2])
    elif len(arguments) == 1:
        from worker.consumer import consume

        consume(arguments[0])
    else:
        sys.exit("usage: worker.py <ingest|studio|plugins>")
