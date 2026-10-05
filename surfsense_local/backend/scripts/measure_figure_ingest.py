"""Measure what keeping figures costs ingest: time and memory, without and with.

`SURFSENSE_LOCAL_MODELS_DIR=models uv run scripts/measure_figure_ingest.py report.pdf`
converts the file once per mode, each in a fresh process, so both pay the same
model load and each peak is its own. "without" is ingest before figures were
kept; "with" converts the same way, then crops and saves each figure as ingest does.
Retained is the process's memory afterwards, Docling's reading still held. On a
short file both numbers are mostly the model load; measure a long one too.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

from worker.ingestion.parser_pack import missing_parser_folders

MODES = {"without": False, "with": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--convert", choices=MODES, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.convert:
        convert_once(args.pdf, keep_figures=MODES[args.convert])
        return

    missing = missing_parser_folders()
    if missing:
        # Docling would otherwise download its models mid-measurement.
        sys.exit(
            f"Docling's models are missing ({', '.join(missing)}): run "
            "scripts/fetch_docling_models.py or set SURFSENSE_LOCAL_MODELS_DIR"
        )
    for mode in MODES:
        result = measure(args.pdf, mode)
        print(
            f"{mode} figures: convert {result['convert_seconds']:.1f} s, "
            f"figures {result['figure_seconds']:.1f} s, "
            f"retained {result['retained_rss'] / 2**20:.0f} MiB, "
            f"peak {result['peak_rss'] / 2**20:.0f} MiB, "
            f"{result['pages']} pages, {result['pictures']} pictures, "
            f"{result['figures']} figures kept"
        )


def measure(pdf: Path, mode: str) -> dict:
    child = subprocess.run(
        [sys.executable, __file__, str(pdf), "--convert", mode],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if child.returncode != 0:
        sys.exit(child.stderr[-4000:])
    return json.loads(child.stdout.strip().splitlines()[-1])


def convert_once(pdf: Path, *, keep_figures: bool) -> None:
    from worker.ingestion.parsing import convert

    started = time.perf_counter()
    document = convert(pdf)
    convert_seconds = time.perf_counter() - started  # includes loading the models

    started = time.perf_counter()
    figures = save_figures(pdf, document) if keep_figures else 0
    figure_seconds = time.perf_counter() - started

    print(
        json.dumps(
            {
                "convert_seconds": convert_seconds,
                "figure_seconds": figure_seconds,
                "retained_rss": psutil.Process().memory_info().rss,
                "peak_rss": peak_rss(),
                "pages": len(document.pages),
                "pictures": len(document.pictures),
                "figures": figures,
            }
        )
    )


def save_figures(pdf: Path, document: object) -> int:
    """Crop and save every figure as ingest does, into a folder thrown away after."""
    from worker.ingestion.figures.pictures import pictures_in

    with tempfile.TemporaryDirectory() as folder:
        saved = 0
        for saved, picture in enumerate(pictures_in(pdf, document), start=1):
            picture.image.save(Path(folder) / f"{saved}.png", "PNG")
        return saved


def peak_rss() -> int:
    """This process's peak resident memory in bytes, as the OS counted it."""
    if sys.platform == "win32":
        return psutil.Process().memory_info().peak_wset
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024  # Linux counts KiB


if __name__ == "__main__":
    main()
