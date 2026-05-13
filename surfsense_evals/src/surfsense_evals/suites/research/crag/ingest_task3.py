"""CRAG Task 3 ingestion: 4-part download → streaming JSONL → upload.

Same flow as ``ingest.run_ingest`` for Tasks 1 & 2 (extract HTML →
upload markdown → resolve doc_ids → write doc map), but:

* Source: 4 .tar.bz2 parts streamed via ``dataset_task3``.
* Page count: 50 per question instead of 5 — the whole point of
  Task 3 (the long-context arm now structurally has to choose what
  to keep, while SurfSense's retrieval becomes mandatory).
* Stratified sampling re-uses the Task 1 helper since the question
  schema is identical.

Doc map lands at ``<suite_data>/maps/crag_t3_doc_map.jsonl`` with the
same row shape as Task 1's map (so the runner only needs to know
which file to load; everything else is shared).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ....core.config import set_suite_state
from ....core.ingest_settings import IngestSettings, settings_header_line
from ....core.registry import RunContext
from .dataset import stratified_sample, write_questions_jsonl
from .dataset_task3 import (
    CRAG_TASK_3_PART_NAMES,
    iter_questions_task3,
    parts_present,
)
from .ingest import (
    _IngestStats,
    _materialise_pages,
    _resolve_question_doc_ids,
    _upload_pages,
)

logger = logging.getLogger(__name__)


_INSTRUCTIONS_TO_DOWNLOAD = (
    "Run `python scripts/download_crag_task3.py` first to fetch the "
    "4 tar.bz2 parts (~7 GB total) into "
    "data/research/crag_t3/.raw_cache/. The downloader is idempotent "
    "and parallel."
)


async def run_ingest_task3(
    ctx: RunContext,
    *,
    n_questions: int | None = None,
    upload_batch_size: int = 16,
    skip_upload: bool = False,
    overwrite_extract: bool = False,
    settings: IngestSettings | None = None,
    sample_seed: int = 17,
    parse_cap: int | None = None,
) -> None:
    """Ingest CRAG Task 3 (50 pages per question) into the research suite.

    Parameters
    ----------
    n_questions
        Cap on the post-stratified-sample question count. ``None`` =
        "use whatever ``parse_cap`` produced". For real runs aim for
        50 (~2,500 pages) — n=200 (10k pages) is doable but slow.
    parse_cap
        Hard cap on how many rows we *parse* from the streaming
        archive before stratified sampling. Defaults to
        ``max(400, 6*n_questions)`` — enough to cover all (domain,
        question_type) buckets ~5x but small enough to fit in the
        first shard or two (each shard is ≈5 GB decompressed and
        holds ~300 rows; bz2 throughput is ~50 MB/s). Lowering this
        is the only knob that bounds streaming cost since we can
        ``break`` out of the JSONL stream early without decompressing
        the rest of the ~50 GB archive body.
    upload_batch_size
        Markdown files per ``/documents/fileupload`` call.
    skip_upload
        Extract markdown locally, don't push to SurfSense.
    overwrite_extract
        Re-run trafilatura even when a cached markdown is present.
    settings
        Per-upload knobs override (default: text-only basic ETL).
    sample_seed
        RNG seed for stratified sampling (deterministic).
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

    if not parts_present(raw_cache):
        missing = [
            n for n in CRAG_TASK_3_PART_NAMES
            if not (raw_cache / n).exists()
        ]
        raise RuntimeError(
            f"CRAG Task 3 parts missing from {raw_cache}: {missing}. "
            f"{_INSTRUCTIONS_TO_DOWNLOAD}"
        )

    # 1. Stream-parse (capped). For n=50 we don't need the full 2,706
    #    rows — just enough that the stratified sampler can balance.
    #    Each tar shard ~5 GB / ~300 rows / ~2 min decompress, so
    #    400-500 rows = shard 0 + a slice of shard 1 ≈ 3-4 min.
    parse_cap = parse_cap or (
        max(400, 6 * (n_questions or 50)) if n_questions else None
    )
    logger.info(
        "CRAG Task 3: streaming JSONL (parse_cap=%s) ...",
        parse_cap if parse_cap else "no-cap",
    )
    all_questions = iter_questions_task3(raw_cache, max_questions=parse_cap)
    logger.info("CRAG Task 3: parsed %d rows", len(all_questions))

    if not all_questions:
        raise RuntimeError("CRAG Task 3 streaming returned 0 rows; check archive integrity.")

    if n_questions is not None and n_questions > 0:
        questions = stratified_sample(all_questions, n=n_questions, seed=sample_seed)
        logger.info(
            "CRAG Task 3: stratified sample of %d questions across %d (domain, qtype) buckets",
            len(questions),
            len({(q.domain, q.question_type) for q in questions}),
        )
    else:
        questions = all_questions

    questions_jsonl = bench_dir / "questions.jsonl"
    write_questions_jsonl(questions, questions_jsonl)

    n_pages_total = sum(len(q.pages) for q in questions)
    logger.info(
        "CRAG Task 3: extracting up to %d pages across %d questions ...",
        n_pages_total, len(questions),
    )
    qid_to_files, _file_to_url = _materialise_pages(
        questions, pages_dir=pages_dir, overwrite=overwrite_extract,
    )
    n_pages_extracted = sum(len(v) for v in qid_to_files.values())

    name_to_id: dict[str, int] = {}
    if skip_upload:
        logger.info("CRAG Task 3: --skip-upload; skipping SurfSense ingestion")
    else:
        all_filenames = sorted({fn for fns in qid_to_files.values() for fn in fns})
        logger.info("CRAG Task 3: uploading %d unique pages ...", len(all_filenames))
        name_to_id = await _upload_pages(
            ctx,
            pages_dir=pages_dir,
            filenames=all_filenames,
            batch_size=upload_batch_size,
            settings=settings,
        )

    doc_rows = _resolve_question_doc_ids(questions, qid_to_files, name_to_id)
    map_path = ctx.maps_dir() / "crag_t3_doc_map.jsonl"
    with map_path.open("w", encoding="utf-8") as fh:
        fh.write(settings_header_line(settings) + "\n")
        for row in doc_rows:
            fh.write(json.dumps(row) + "\n")
    logger.info("Wrote CRAG Task 3 doc map to %s (%d rows)", map_path, len(doc_rows))

    new_state = ctx.suite_state
    new_state.ingestion_maps["crag_t3"] = str(map_path)
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
    logger.info("CRAG Task 3 ingest done: %s", stats)


__all__ = ["run_ingest_task3"]
