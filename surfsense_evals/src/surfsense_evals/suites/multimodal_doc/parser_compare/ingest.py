"""parser_compare ingestion: pre-extract markdown 4 ways per PDF.

For each PDF in scope, we run all four (parser × mode) combinations
in parallel and persist the resulting markdown alongside the PDF:

    data/multimodal_doc/parser_compare/extractions/
      <doc_id>.azure_basic.md
      <doc_id>.azure_premium.md
      <doc_id>.llamacloud_basic.md
      <doc_id>.llamacloud_premium.md

A manifest at ``maps/parser_compare_doc_map.jsonl`` records, per PDF:

* ``doc_id``         — filename of the source PDF.
* ``pdf_path``       — local cached PDF path.
* ``document_id``    — SurfSense document id (carried over from
                        mmlongbench's existing ingestion so the
                        SurfSense agentic arm can scope retrieval).
* ``pages``          — page count via pypdf (drives preprocessing cost).
* ``extractions``    — map of ``arm_name -> {markdown_path, chars,
                        elapsed_s, status, error}``.

The runner reads this manifest, loads the markdown for each long-context
arm, and uses ``document_id`` for the SurfSense arm.

Source PDFs come from the existing mmlongbench ingestion — no new
download or upload happens here. The point of this benchmark is
parser quality on the same physical PDFs SurfSense already has, so
re-using mmlongbench's PDF cache is correct.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ....core.config import set_suite_state
from ....core.parsers import (
    count_pdf_pages,
    parse_with_azure_di,
    parse_with_llamacloud,
)
from ....core.registry import RunContext

logger = logging.getLogger(__name__)


# Order matters for the manifest only (deterministic JSONL diffs);
# the runner doesn't rely on it.
PARSER_ARMS: tuple[tuple[str, str, str], ...] = (
    ("azure_basic_lc", "azure", "basic"),
    ("azure_premium_lc", "azure", "premium"),
    ("llamacloud_basic_lc", "llamacloud", "basic"),
    ("llamacloud_premium_lc", "llamacloud", "premium"),
)


@dataclass
class ExtractionResult:
    arm: str
    parser: str
    mode: str
    markdown_path: Path | None = None
    chars: int = 0
    elapsed_s: float = 0.0
    status: str = "ok"  # "ok" | "failed"
    error: str | None = None

    def to_jsonl(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "parser": self.parser,
            "mode": self.mode,
            "markdown_path": str(self.markdown_path) if self.markdown_path else None,
            "chars": self.chars,
            "elapsed_s": round(self.elapsed_s, 2),
            "status": self.status,
            "error": self.error,
        }


@dataclass
class PdfManifestRow:
    doc_id: str
    pdf_path: Path
    document_id: int | None
    pages: int
    extractions: dict[str, ExtractionResult] = field(default_factory=dict)

    def to_jsonl(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "pdf_path": str(self.pdf_path),
            "document_id": self.document_id,
            "pages": self.pages,
            "extractions": {arm: ext.to_jsonl() for arm, ext in self.extractions.items()},
        }


# ---------------------------------------------------------------------------
# Single-PDF extraction
# ---------------------------------------------------------------------------


async def _run_one_extraction(
    pdf_path: Path,
    *,
    parser: str,
    mode: str,
    out_path: Path,
    estimated_pages: int,
) -> tuple[str, float]:
    """Invoke the requested parser, persist markdown, return (markdown, elapsed_s)."""

    started = time.monotonic()
    if parser == "azure":
        markdown = await parse_with_azure_di(pdf_path, processing_mode=mode)
    elif parser == "llamacloud":
        markdown = await parse_with_llamacloud(
            pdf_path,
            processing_mode=mode,
            estimated_pages=estimated_pages,
        )
    else:
        raise ValueError(f"Unknown parser {parser!r}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(out_path.write_text, markdown, encoding="utf-8")
    return markdown, time.monotonic() - started


async def _extract_one_pdf(
    pdf_path: Path,
    *,
    extractions_dir: Path,
    force_reextract: bool,
) -> dict[str, ExtractionResult]:
    """Run all four parser combos for ``pdf_path``, returning per-arm results.

    Re-uses any cached ``.md`` already on disk unless ``force_reextract``.
    The four parser invocations run concurrently — they're independent
    HTTP-bound jobs and the providers don't share state.
    """

    estimated_pages = count_pdf_pages(pdf_path) or 50
    out: dict[str, ExtractionResult] = {}
    coros = []
    arm_specs: list[tuple[str, str, str, Path]] = []

    for arm_name, parser, mode in PARSER_ARMS:
        out_path = extractions_dir / f"{pdf_path.stem}.{arm_name}.md"
        arm_specs.append((arm_name, parser, mode, out_path))

        if out_path.exists() and not force_reextract:
            cached = out_path.read_text(encoding="utf-8")
            out[arm_name] = ExtractionResult(
                arm=arm_name,
                parser=parser,
                mode=mode,
                markdown_path=out_path,
                chars=len(cached),
                elapsed_s=0.0,
                status="ok",
                error="(cached)",
            )
            logger.info(
                "Cached extraction reused: %s (%d chars)",
                out_path.name,
                len(cached),
            )
            coros.append(_noop())
        else:
            coros.append(
                _run_one_extraction(
                    pdf_path,
                    parser=parser,
                    mode=mode,
                    out_path=out_path,
                    estimated_pages=estimated_pages,
                )
            )

    results = await asyncio.gather(*coros, return_exceptions=True)
    for (arm_name, parser, mode, out_path), result in zip(arm_specs, results, strict=True):
        if arm_name in out:
            continue  # cached — already populated above
        if isinstance(result, Exception):
            err = result
            err_msg = f"{type(err).__name__}: {err}"
            logger.warning(
                "Extraction FAILED for %s [%s/%s]: %s",
                pdf_path.name,
                parser,
                mode,
                err_msg,
            )
            out[arm_name] = ExtractionResult(
                arm=arm_name,
                parser=parser,
                mode=mode,
                status="failed",
                error=err_msg,
            )
        else:
            markdown, elapsed = result
            out[arm_name] = ExtractionResult(
                arm=arm_name,
                parser=parser,
                mode=mode,
                markdown_path=out_path,
                chars=len(markdown),
                elapsed_s=elapsed,
                status="ok",
            )
    return out


async def _noop() -> tuple[str, float]:
    """Placeholder so cached entries align with parallel gather indexing."""

    return ("", 0.0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _read_existing_mmlongbench_map(map_path: Path) -> list[dict[str, Any]]:
    """Read the mmlongbench doc map (skipping its ``__settings__`` header)."""

    if not map_path.exists():
        raise RuntimeError(
            f"mmlongbench doc map not found at {map_path}. Run "
            "`python -m surfsense_evals ingest multimodal_doc mmlongbench` first."
        )
    rows: list[dict[str, Any]] = []
    with map_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "__settings__" in row:
                continue
            rows.append(row)
    return rows


async def run_ingest(
    ctx: RunContext,
    *,
    docs_filter: list[str] | None = None,
    max_docs: int | None = None,
    force_reextract: bool = False,
    pdf_concurrency: int = 2,
) -> None:
    """Pre-extract all four parser markdowns for each PDF.

    Parameters
    ----------
    docs_filter : list[str] | None
        Specific filenames to extract (default: all PDFs from
        mmlongbench's existing manifest).
    max_docs : int | None
        Cap on number of PDFs to process. Default: all.
    force_reextract : bool
        Re-call parsers even if a cached ``.md`` already exists. Off
        by default — extractions are deterministic and parser calls
        cost real money.
    pdf_concurrency : int
        How many PDFs to extract in parallel. Each PDF triggers four
        parser HTTP calls, so total in-flight = 4 * pdf_concurrency.
        Default 2 keeps us comfortably under both Azure DI and
        LlamaCloud per-IP rate limits.
    """

    # Pull the source PDFs and document_ids from mmlongbench's existing
    # ingestion. parser_compare doesn't re-upload; SurfSense's agentic
    # arm queries the same search_space=55 chunks.
    mmlb_map = ctx.suite_state.ingestion_maps.get("mmlongbench")
    if not mmlb_map:
        raise RuntimeError(
            "Suite state has no mmlongbench ingestion map. Run "
            "`python -m surfsense_evals ingest multimodal_doc mmlongbench` first "
            "so parser_compare can re-use those PDFs."
        )
    src_rows = _read_existing_mmlongbench_map(Path(mmlb_map))

    rows_in_scope = src_rows
    if docs_filter:
        wanted = set(docs_filter)
        rows_in_scope = [r for r in rows_in_scope if r["doc_id"] in wanted]
    if max_docs is not None and max_docs > 0:
        rows_in_scope = rows_in_scope[:max_docs]

    if not rows_in_scope:
        raise RuntimeError("No PDFs in scope for parser_compare. Check --docs / --max-docs.")

    bench_dir = ctx.benchmark_data_dir()
    extractions_dir = bench_dir / "extractions"
    extractions_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(max(1, pdf_concurrency))
    manifest_rows: list[PdfManifestRow] = []

    async def _process(row: dict[str, Any]) -> PdfManifestRow:
        pdf_path = Path(row["pdf_path"])
        async with sem:
            extractions = await _extract_one_pdf(
                pdf_path,
                extractions_dir=extractions_dir,
                force_reextract=force_reextract,
            )
        return PdfManifestRow(
            doc_id=str(row["doc_id"]),
            pdf_path=pdf_path,
            document_id=row.get("document_id"),
            pages=count_pdf_pages(pdf_path),
            extractions=extractions,
        )

    logger.info(
        "parser_compare: extracting %d PDFs x 4 parsers (concurrency=%d)",
        len(rows_in_scope),
        pdf_concurrency,
    )
    manifest_rows = await asyncio.gather(*(_process(r) for r in rows_in_scope))

    # Persist manifest
    map_path = ctx.maps_dir() / "parser_compare_doc_map.jsonl"
    with map_path.open("w", encoding="utf-8") as fh:
        for mr in manifest_rows:
            fh.write(json.dumps(mr.to_jsonl()) + "\n")
    logger.info("parser_compare manifest -> %s", map_path)

    # Update suite state so the runner can find us via
    # ctx.suite_state.ingestion_maps.
    new_state = ctx.suite_state
    new_state.ingestion_maps["parser_compare"] = str(map_path)
    set_suite_state(ctx.config, ctx.suite, new_state)

    # Quick summary log
    total_extractions = sum(len(mr.extractions) for mr in manifest_rows)
    failures = sum(
        1 for mr in manifest_rows for ext in mr.extractions.values() if ext.status != "ok"
    )
    logger.info(
        "parser_compare ingest done: %d PDFs, %d extractions, %d failures",
        len(manifest_rows),
        total_extractions,
        failures,
    )


__all__ = [
    "ExtractionResult",
    "PARSER_ARMS",
    "PdfManifestRow",
    "run_ingest",
]
