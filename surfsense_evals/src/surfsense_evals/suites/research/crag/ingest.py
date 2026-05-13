"""CRAG ingestion: download → extract → upload → per-question doc map.

Steps:

1. Download ``crag_task_1_and_2_dev_v4.jsonl.bz2`` from
   ``facebookresearch/CRAG`` (skip if cached).
2. Stream-parse into ``CragQuestion`` objects.
3. Optionally cap to ``--n-questions N`` (and *stratified* sample
   across ``(domain, question_type)`` so the smoke / partial run
   isn't dominated by ``finance`` or ``simple``).
4. For each question, extract the 5 web pages to clean markdown via
   ``trafilatura`` and write them to
   ``<bench_dir>/pages/<qid>__<page_idx>__<url_hash>.md``. The
   filename is unique across the whole sample (so SurfSense's
   ``(filename, search_space)`` dedup never collides between
   questions) and round-trippable (the ``<qid>__`` prefix lets the
   ingest infer doc-membership at the title level even before we
   land on a stable status response).
5. Upload all extracted pages to SurfSense in batches with text-only
   ETL (``use_vision_llm=False, processing_mode="basic"``) — these
   are extracted plaintext, no images involved.
6. Persist a doc map at
   ``<suite_data>/maps/crag_doc_map.jsonl`` with one row per question:

       {"qid": "C00042",
        "interaction_id": "<uuid>",
        "question": "<text>",
        "gold_answer": "<text>",
        "alt_answers": [...],
        "domain": "...", "question_type": "...",
        "static_or_dynamic": "...", "popularity": "...",
        "query_time": "...",
        "page_filenames": ["C00042__0__abc123.md", ...],
        "document_ids": [42101, 42102, ...],
        "missing_pages": [...]   # filenames whose upload failed
       }

The runner uses ``document_ids`` to scope SurfSense retrieval to
exactly the 5 pages of the question (matches CRAG protocol — the
benchmark explicitly hands over its own retrieved pages).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....core.clients.documents import (
    DocumentProcessingFailed,
    DocumentProcessingTimeout,
)
from ....core.config import set_suite_state
from ....core.ingest_settings import IngestSettings, settings_header_line
from ....core.registry import RunContext
from .dataset import (
    CragPage,
    CragQuestion,
    download_task_1_2,
    iter_questions,
    stratified_sample,
    write_questions_jsonl,
)
from .html_extract import extract_main_content

logger = logging.getLogger(__name__)


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._\-]+")


def _page_filename(qid: str, page_idx: int, page: CragPage) -> str:
    """Filesystem-safe, globally unique markdown filename for a CRAG page.

    Format: ``<qid>__<idx>__<url_hash>.md``. Both the qid (``C00042``)
    and the URL-hash (``[:12]``) are alphanumeric so we don't need to
    sanitise them, but we strip anything else just in case.
    """

    qid_safe = _FILENAME_SAFE.sub("_", qid)
    return f"{qid_safe}__{page_idx:02d}__{page.url_hash}.md"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@dataclass
class _IngestStats:
    n_questions: int
    n_pages_total: int
    n_pages_extracted: int
    n_pages_empty: int
    n_uploaded: int
    n_existing: int
    bench_dir: Path
    map_path: Path


# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------


def _materialise_pages(
    questions: list[CragQuestion],
    *,
    pages_dir: Path,
    overwrite: bool = False,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Extract every page in every question to ``pages_dir`` as markdown.

    Returns:
      * ``qid -> [filename, filename, ...]`` (in page order, only
        successful extractions)
      * ``filename -> source_url`` for diagnostics

    Empty extractions (paywall / JS / parse-fail with no fallback
    output) are skipped — better to retrieve from 4 pages than feed
    SurfSense's chunker an empty file.
    """

    pages_dir.mkdir(parents=True, exist_ok=True)
    qid_to_files: dict[str, list[str]] = {}
    file_to_url: dict[str, str] = {}
    method_counts: dict[str, int] = {}
    n_empty = 0

    for q in questions:
        names: list[str] = []
        for idx, page in enumerate(q.pages):
            filename = _page_filename(q.qid, idx, page)
            dest = pages_dir / filename
            if dest.exists() and dest.stat().st_size > 0 and not overwrite:
                method_counts["cache_hit"] = method_counts.get("cache_hit", 0) + 1
                names.append(filename)
                file_to_url[filename] = page.page_url
                continue
            result = extract_main_content(
                page.page_html,
                url=page.page_url,
                page_name=page.page_name,
                last_modified=page.page_last_modified,
            )
            method_counts[result.method] = method_counts.get(result.method, 0) + 1
            if not result.ok:
                n_empty += 1
                continue
            dest.write_text(result.text, encoding="utf-8")
            names.append(filename)
            file_to_url[filename] = page.page_url
        qid_to_files[q.qid] = names

    logger.info(
        "CRAG page extraction: %s; empty=%d, total_files=%d across %d questions",
        method_counts, n_empty, len(file_to_url), len(qid_to_files),
    )
    return qid_to_files, file_to_url


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


async def _upload_pages(
    ctx: RunContext,
    *,
    pages_dir: Path,
    filenames: list[str],
    batch_size: int,
    settings: IngestSettings,
) -> dict[str, int]:
    """Upload ``filenames`` (already on disk under ``pages_dir``) and return name → doc_id."""

    if not filenames:
        return {}
    docs_client = ctx.documents_client()
    name_to_id: dict[str, int] = {}
    paths = [pages_dir / fn for fn in filenames if (pages_dir / fn).exists()]

    for batch_start in range(0, len(paths), batch_size):
        batch = paths[batch_start : batch_start + batch_size]
        result = await docs_client.upload(
            files=batch,
            search_space_id=ctx.search_space_id,
            should_summarize=settings.should_summarize,
            use_vision_llm=settings.use_vision_llm,
            processing_mode=settings.processing_mode,
        )
        all_ids = list(result.document_ids) + list(result.duplicate_document_ids)
        if result.document_ids:
            try:
                await docs_client.wait_until_ready(
                    search_space_id=ctx.search_space_id,
                    document_ids=result.document_ids,
                    timeout_s=900.0,
                )
            except (DocumentProcessingFailed, DocumentProcessingTimeout) as exc:
                logger.warning("CRAG batch processing issue: %s", exc)
        if all_ids:
            statuses = await docs_client.get_status(
                search_space_id=ctx.search_space_id,
                document_ids=all_ids,
            )
            for s in statuses:
                stem = Path(s.title).stem if s.title.endswith(".md") else s.title
                name_to_id[stem] = s.document_id
                name_to_id[s.title] = s.document_id
                if not s.title.endswith(".md"):
                    name_to_id[f"{s.title}.md"] = s.document_id
        logger.info(
            "CRAG upload batch %d-%d: %d new, %d duplicate",
            batch_start, batch_start + len(batch),
            len(result.document_ids), len(result.duplicate_document_ids),
        )
    return name_to_id


# ---------------------------------------------------------------------------
# Doc map writer
# ---------------------------------------------------------------------------


def _resolve_question_doc_ids(
    questions: list[CragQuestion],
    qid_to_files: dict[str, list[str]],
    name_to_id: dict[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for q in questions:
        filenames = qid_to_files.get(q.qid, [])
        doc_ids: list[int] = []
        missing: list[str] = []
        for fn in filenames:
            stem = Path(fn).stem
            doc_id = name_to_id.get(stem) or name_to_id.get(fn)
            if doc_id is not None and doc_id not in doc_ids:
                doc_ids.append(doc_id)
            else:
                missing.append(fn)
        rows.append({
            "qid": q.qid,
            "interaction_id": q.interaction_id,
            "raw_index": q.raw_index,
            "question": q.query,
            "gold_answer": q.gold_answer,
            "alt_answers": list(q.alt_answers),
            "domain": q.domain,
            "question_type": q.question_type,
            "static_or_dynamic": q.static_or_dynamic,
            "popularity": q.popularity,
            "query_time": q.query_time,
            "split": q.split,
            "page_filenames": filenames,
            "document_ids": doc_ids,
            "missing_pages": missing,
            "n_pages": len(filenames),
        })
    return rows


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run_ingest(
    ctx: RunContext,
    *,
    n_questions: int | None = None,
    upload_batch_size: int = 16,
    skip_upload: bool = False,
    overwrite_extract: bool = False,
    settings: IngestSettings | None = None,
    sample_seed: int = 17,
) -> None:
    """Ingest the CRAG benchmark (Tasks 1 & 2) into the research suite.

    Parameters
    ----------
    n_questions
        Cap on the number of CRAG questions to materialise.
        ``None`` = all 2,706 (~13,500 pages — large; smoke runs
        should pass 10-20 and full runs ~200).
    upload_batch_size
        Markdown files per ``/documents/fileupload`` call.
    skip_upload
        Extract + cache markdown locally but don't push to SurfSense
        (useful for debugging the extraction step).
    overwrite_extract
        Re-run trafilatura even when a cached markdown file exists.
        Default False so re-running ingest is idempotent.
    settings
        Override per-upload knobs. CRAG defaults to text-only basic
        ETL — these are *extracted* plaintext, no images.
    sample_seed
        RNG seed for ``stratified_sample``. Pin this for reproducibility.
    """

    settings = settings or IngestSettings(
        use_vision_llm=False,
        processing_mode="basic",
        should_summarize=False,
    )
    bench_dir = ctx.benchmark_data_dir()
    pages_dir = bench_dir / "pages"
    raw_cache = bench_dir / ".raw_cache"
    raw_cache.mkdir(parents=True, exist_ok=True)

    bz2_path = download_task_1_2(raw_cache)
    logger.info("CRAG: parsing %s ...", bz2_path.name)
    all_questions = iter_questions(bz2_path)
    if not all_questions:
        raise RuntimeError(
            "CRAG JSONL contained no parseable rows; upstream may have changed schema."
        )
    logger.info("CRAG: parsed %d total questions", len(all_questions))

    if n_questions is not None and n_questions > 0:
        questions = stratified_sample(all_questions, n=n_questions, seed=sample_seed)
        logger.info(
            "CRAG: stratified sample of %d questions across %d (domain, qtype) buckets",
            len(questions),
            len({(q.domain, q.question_type) for q in questions}),
        )
    else:
        questions = all_questions

    questions_jsonl = bench_dir / "questions.jsonl"
    write_questions_jsonl(questions, questions_jsonl)

    n_pages_total = sum(len(q.pages) for q in questions)
    logger.info(
        "CRAG: extracting up to %d pages across %d questions ...",
        n_pages_total, len(questions),
    )
    qid_to_files, file_to_url = _materialise_pages(
        questions, pages_dir=pages_dir, overwrite=overwrite_extract,
    )
    n_pages_extracted = sum(len(v) for v in qid_to_files.values())

    name_to_id: dict[str, int] = {}
    if skip_upload:
        logger.info("CRAG: --skip-upload; skipping SurfSense ingestion")
    else:
        all_filenames = sorted({fn for fns in qid_to_files.values() for fn in fns})
        logger.info("CRAG: uploading %d unique pages ...", len(all_filenames))
        name_to_id = await _upload_pages(
            ctx,
            pages_dir=pages_dir,
            filenames=all_filenames,
            batch_size=upload_batch_size,
            settings=settings,
        )

    doc_rows = _resolve_question_doc_ids(questions, qid_to_files, name_to_id)
    map_path = ctx.maps_dir() / "crag_doc_map.jsonl"
    with map_path.open("w", encoding="utf-8") as fh:
        fh.write(settings_header_line(settings) + "\n")
        for row in doc_rows:
            fh.write(json.dumps(row) + "\n")
    logger.info("Wrote CRAG doc map to %s (%d rows)", map_path, len(doc_rows))

    new_state = ctx.suite_state
    new_state.ingestion_maps["crag"] = str(map_path)
    set_suite_state(ctx.config, ctx.suite, new_state)

    stats = _IngestStats(
        n_questions=len(questions),
        n_pages_total=n_pages_total,
        n_pages_extracted=n_pages_extracted,
        n_pages_empty=n_pages_total - n_pages_extracted,
        n_uploaded=len(name_to_id),
        n_existing=0,
        bench_dir=bench_dir,
        map_path=map_path,
    )
    logger.info("CRAG ingest done: %s", stats)


# ---------------------------------------------------------------------------
# For runner: read extracted page text back from disk
# ---------------------------------------------------------------------------


def read_page_markdown(bench_dir: Path, filename: str) -> str | None:
    """Return the on-disk markdown body for a previously-extracted page.

    Used by the long-context runner arm to assemble the prompt at
    inference time — we don't keep all 5×N pages in memory between
    ingest and run.
    """

    path = bench_dir / "pages" / filename
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


async def _retry_upload_idempotent(  # noqa: D401 - hidden helper
    ctx: RunContext,
    *,
    pages_dir: Path,
    filenames: list[str],
    batch_size: int,
    settings: IngestSettings,
    max_attempts: int = 2,
) -> dict[str, int]:
    """Future-proofing hook (unused today): retry the ingest upload pass."""

    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await _upload_pages(
                ctx,
                pages_dir=pages_dir,
                filenames=filenames,
                batch_size=batch_size,
                settings=settings,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("CRAG upload attempt %d failed: %s", attempt + 1, exc)
            await asyncio.sleep(2.0 * (attempt + 1))
    if last_exc is not None:
        raise last_exc
    return {}


__all__ = [
    "_IngestStats",
    "_materialise_pages",
    "_page_filename",
    "_resolve_question_doc_ids",
    "_upload_pages",
    "read_page_markdown",
    "run_ingest",
]
