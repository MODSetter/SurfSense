"""MMLongBench-Doc ingestion.

Steps:

1. Pull the questions parquet from
   ``hf://datasets/yubo2333/MMLongBench-Doc/data/`` and cache locally.
2. Resolve the unique set of ``doc_id`` referenced by questions, and
   download each PDF from
   ``hf://datasets/yubo2333/MMLongBench-Doc/documents/<doc_id>``.
   ``huggingface_hub.hf_hub_download`` is resumable + content-hash
   verifying; we cache PDFs under ``<data_dir>/multimodal_doc/mmlongbench/pdfs/``.
3. Upload every PDF to SurfSense via ``DocumentsClient.upload`` with
   ``use_vision_llm=True`` so SurfSense's Pillow + LiteLLM vision
   pipeline extracts captions / OCR for embedded images, charts, and
   tables.
4. Wait for ``processed`` status and persist
   ``doc_id -> document_id`` in
   ``<data_dir>/multimodal_doc/maps/mmlongbench_doc_map.jsonl``.

By default we ingest **all** 135 PDFs (~660 MB, totally manageable).
Operators can scope to a subset with ``--max-docs N`` if iterating on
a slow vision pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ....core.config import set_suite_state
from ....core.ingest_settings import IngestSettings, settings_header_line
from ....core.registry import RunContext

logger = logging.getLogger(__name__)


HF_REPO_ID = "yubo2333/MMLongBench-Doc"
HF_REPO_TYPE = "dataset"


# Lazy import: huggingface_hub + pyarrow are heavyweight; keep the
# benchmark module importable on machines that have only the core
# install (e.g. CI lint jobs).
def _hf_hub_download(*args, **kwargs):
    from huggingface_hub import hf_hub_download

    return hf_hub_download(*args, **kwargs)


def _list_repo_files() -> list[str]:
    from huggingface_hub import list_repo_files

    return list_repo_files(repo_id=HF_REPO_ID, repo_type=HF_REPO_TYPE)


# ---------------------------------------------------------------------------
# Question parquet -> Python rows
# ---------------------------------------------------------------------------


@dataclass
class MMLongBenchQuestion:
    doc_id: str  # filename inside the documents/ folder
    doc_type: str
    question: str
    answer: str
    answer_format: str  # Str / Int / Float / List / None
    evidence_pages: list[int]
    evidence_sources: list[str]


def _load_questions_from_parquet(parquet_path: Path) -> list[MMLongBenchQuestion]:
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    out: list[MMLongBenchQuestion] = []
    for row in rows:
        doc_id = str(row.get("doc_id") or "").strip()
        if not doc_id:
            continue
        question = str(row.get("question") or "").strip()
        if not question:
            continue
        out.append(
            MMLongBenchQuestion(
                doc_id=doc_id,
                doc_type=str(row.get("doc_type") or "").strip(),
                question=question,
                answer=str(row.get("answer") or "").strip(),
                answer_format=str(row.get("answer_format") or "").strip(),
                evidence_pages=_parse_int_list(row.get("evidence_pages")),
                evidence_sources=_parse_str_list(row.get("evidence_sources")),
            )
        )
    return out


def _parse_int_list(raw) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out = []
        for x in raw:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    text = str(raw).strip().strip("[]")
    if not text:
        return []
    out: list[int] = []
    for tok in text.split(","):
        tok = tok.strip().strip("'\"")
        if tok.isdigit():
            out.append(int(tok))
    return out


def _parse_str_list(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip().strip("'\"") for x in raw if str(x).strip()]
    text = str(raw).strip().strip("[]")
    if not text:
        return []
    return [tok.strip().strip("'\"") for tok in text.split(",") if tok.strip()]


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def _download_questions_parquet(cache_dir: Path) -> Path:
    """Download every parquet under ``data/`` and concatenate.

    The HF dataset usually publishes a single ``train`` split, but we
    enumerate to be robust to repo restructuring.
    """

    parquet_paths: list[Path] = []
    files = _list_repo_files()
    data_files = [f for f in files if f.startswith("data/") and f.endswith(".parquet")]
    if not data_files:
        raise RuntimeError(
            f"No parquet files found under data/ in {HF_REPO_ID}; "
            f"upstream repo may have been restructured."
        )
    for rel in sorted(data_files):
        local = _hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=rel,
            repo_type=HF_REPO_TYPE,
            cache_dir=str(cache_dir),
        )
        parquet_paths.append(Path(local))
        logger.info("Cached MMLongBench parquet shard %s -> %s", rel, local)
    return (
        parquet_paths[0] if len(parquet_paths) == 1 else _merge_parquets(parquet_paths, cache_dir)
    )


def _merge_parquets(paths: list[Path], cache_dir: Path) -> Path:
    """Combine multiple parquet shards into one (rare branch, but correct)."""

    import pyarrow as pa
    import pyarrow.parquet as pq

    tables = [pq.read_table(p) for p in paths]
    merged = pa.concat_tables(tables, promote_options="default")
    out = cache_dir / "merged_questions.parquet"
    pq.write_table(merged, out)
    return out


def _download_pdf(doc_id: str, cache_dir: Path, pdfs_dir: Path) -> Path:
    """Download a single PDF (resumable via huggingface_hub cache)."""

    rel = f"documents/{doc_id}"
    local = _hf_hub_download(
        repo_id=HF_REPO_ID,
        filename=rel,
        repo_type=HF_REPO_TYPE,
        cache_dir=str(cache_dir),
    )
    # Materialise to a stable path inside our data/ tree so the runner
    # has a deterministic location regardless of HF cache internals.
    dest = pdfs_dir / doc_id
    if not dest.exists() or dest.stat().st_size != Path(local).stat().st_size:
        # Use a hardlink when possible (cheap), fall back to copy.
        try:
            if dest.exists():
                dest.unlink()
            os.link(local, dest)
        except OSError:
            from shutil import copy2

            copy2(local, dest)
    return dest


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------


async def _upload_pdfs(
    ctx: RunContext,
    pdf_paths: Iterable[Path],
    *,
    batch_size: int,
    settings: IngestSettings,
) -> dict[str, int]:
    """Upload PDFs in batches, return ``filename -> document_id`` map."""

    docs_client = ctx.documents_client()
    name_to_id: dict[str, int] = {}
    pdf_list = list(pdf_paths)
    for batch_start in range(0, len(pdf_list), batch_size):
        batch = pdf_list[batch_start : batch_start + batch_size]
        result = await docs_client.upload(
            files=batch,
            search_space_id=ctx.search_space_id,
            use_vision_llm=settings.use_vision_llm,
            processing_mode=settings.processing_mode,
        )
        all_ids = list(result.document_ids) + list(result.duplicate_document_ids)
        if all_ids:
            await docs_client.wait_until_ready(
                search_space_id=ctx.search_space_id,
                document_ids=result.document_ids,  # only newly added need polling
                timeout_s=1800.0,  # vision pipeline is slow on long PDFs
            )
            statuses = await docs_client.get_status(
                search_space_id=ctx.search_space_id,
                document_ids=all_ids,
            )
            for s in statuses:
                name_to_id[s.title] = s.document_id
        logger.info(
            "Uploaded MMLongBench batch %d-%d: %d new, %d duplicate",
            batch_start,
            batch_start + len(batch),
            len(result.document_ids),
            len(result.duplicate_document_ids),
        )
    return name_to_id


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_ingest(
    ctx: RunContext,
    *,
    max_docs: int | None = None,
    upload_batch_size: int = 8,
    skip_upload: bool = False,
    settings: IngestSettings | None = None,
) -> None:
    """Ingest MMLongBench-Doc into the multimodal_doc suite.

    Parameters
    ----------
    max_docs : int | None
        Cap the number of PDFs to download + upload. ``None`` = all 135.
        Useful when iterating on the runner without paying for the full
        vision pipeline pass each time.
    upload_batch_size : int
        How many PDFs to send per ``fileupload`` call. Smaller batches
        recover faster from individual failures; larger batches reduce
        round-trip overhead.
    skip_upload : bool
        Download + cache PDFs locally but skip SurfSense ingestion.
        Useful for testing the native arm in isolation.
    """

    settings = settings or IngestSettings(use_vision_llm=True, processing_mode="basic")
    bench_dir = ctx.benchmark_data_dir()
    pdfs_dir = bench_dir / "pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    hf_cache = bench_dir / ".hf_cache"
    hf_cache.mkdir(parents=True, exist_ok=True)

    # Step 1: questions
    parquet_path = _download_questions_parquet(hf_cache)
    questions = _load_questions_from_parquet(parquet_path)
    if not questions:
        raise RuntimeError(
            "MMLongBench-Doc parquet contains no parseable questions. "
            "Upstream may have changed schema."
        )

    # Persist a copy alongside the PDFs so the runner has one place to read.
    questions_jsonl = bench_dir / "questions.jsonl"
    with questions_jsonl.open("w", encoding="utf-8") as fh:
        for q in questions:
            fh.write(
                json.dumps(
                    {
                        "doc_id": q.doc_id,
                        "doc_type": q.doc_type,
                        "question": q.question,
                        "answer": q.answer,
                        "answer_format": q.answer_format,
                        "evidence_pages": q.evidence_pages,
                        "evidence_sources": q.evidence_sources,
                    }
                )
                + "\n"
            )
    logger.info("Wrote %d MMLongBench questions to %s", len(questions), questions_jsonl)

    # Step 2: download unique PDFs
    unique_doc_ids = sorted({q.doc_id for q in questions})
    if max_docs is not None and max_docs > 0:
        unique_doc_ids = unique_doc_ids[:max_docs]
    logger.info("MMLongBench: downloading %d unique PDFs", len(unique_doc_ids))

    pdf_paths: dict[str, Path] = {}
    for i, doc_id in enumerate(unique_doc_ids, start=1):
        try:
            pdf_paths[doc_id] = _download_pdf(doc_id, hf_cache, pdfs_dir)
            if i % 10 == 0:
                logger.info("  ... %d / %d PDFs cached", i, len(unique_doc_ids))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to download MMLongBench PDF %s: %s", doc_id, exc)

    # Step 3: upload to SurfSense
    name_to_id: dict[str, int] = {}
    if skip_upload:
        logger.info("MMLongBench: --skip-upload set; skipping SurfSense ingestion")
    else:
        logger.info("MMLongBench upload settings: %s", settings.render_label())
        name_to_id = await _upload_pdfs(
            ctx,
            pdf_paths.values(),
            batch_size=upload_batch_size,
            settings=settings,
        )

    # Step 4: persist doc_id -> document_id manifest
    map_path = ctx.maps_dir() / "mmlongbench_doc_map.jsonl"
    with map_path.open("w", encoding="utf-8") as fh:
        # Header line records the resolved ingest settings
        # (see core/ingest_settings.py).
        fh.write(settings_header_line(settings) + "\n")
        for doc_id in unique_doc_ids:
            local = pdf_paths.get(doc_id)
            if local is None:
                continue
            fh.write(
                json.dumps(
                    {
                        "doc_id": doc_id,
                        "document_id": name_to_id.get(local.name),
                        "pdf_path": str(local),
                        "n_questions": sum(1 for q in questions if q.doc_id == doc_id),
                    }
                )
                + "\n"
            )
    logger.info("Wrote MMLongBench doc map to %s", map_path)

    new_state = ctx.suite_state
    new_state.ingestion_maps["mmlongbench"] = str(map_path)
    set_suite_state(ctx.config, ctx.suite, new_state)


__all__ = ["MMLongBenchQuestion", "run_ingest"]
