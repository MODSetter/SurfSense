"""MedXpertQA-MM ingestion.

Steps:

1. Pull ``MM/test.jsonl`` (and optionally ``MM/dev.jsonl``) plus
   ``images.zip`` from
   ``hf://datasets/TsinghuaC3I/MedXpertQA``. Cache under
   ``<data_dir>/medical/medxpertqa/``.
2. Extract ``images.zip`` once into ``<data_dir>/medical/medxpertqa/images/``.
3. Render one PDF per MM question (text question + structured patient
   info embedded in the question stem + each image flowable + answer
   options). Output: ``<data_dir>/medical/medxpertqa/pdfs/<id>.pdf``.
4. Upload each PDF to SurfSense with ``use_vision_llm=True``; persist
   ``id -> document_id`` in
   ``<data_dir>/medical/maps/medxpertqa_doc_map.jsonl``.

Both arms then receive byte-identical PDFs. The native arm sends the
PDF directly to OpenRouter; SurfSense ingests via its own vision
pipeline and the runner queries with ``mentioned_document_ids=[...]``
to scope retrieval to the question's PDF.
"""

from __future__ import annotations

import json
import logging
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ....core.config import set_suite_state
from ....core.ingest_settings import IngestSettings, settings_header_line
from ....core.pdf import PdfImage, render_pdf_with_images
from ....core.registry import RunContext
from .prompt import format_options

logger = logging.getLogger(__name__)


HF_REPO_ID = "TsinghuaC3I/MedXpertQA"
HF_REPO_TYPE = "dataset"


def _hf_hub_download(*args, **kwargs):
    from huggingface_hub import hf_hub_download

    return hf_hub_download(*args, **kwargs)


# ---------------------------------------------------------------------------
# Question shape
# ---------------------------------------------------------------------------


@dataclass
class MedXpertQuestion:
    qid: str                         # e.g. "MM-26"
    question: str                    # full question text (case + ask)
    options: dict[str, str]          # A-E
    label: str                       # "A".."E"
    image_files: list[str]           # filenames inside images.zip
    medical_task: str
    body_system: str
    question_type: str
    split: str                       # "test" or "dev"


def _load_jsonl(path: Path, *, split: str) -> list[MedXpertQuestion]:
    out: list[MedXpertQuestion] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            qid = str(row.get("id") or "").strip()
            question = str(row.get("question") or "").strip()
            options = row.get("options") or {}
            label = str(row.get("label") or "").strip().upper()
            if not qid or not question or not isinstance(options, dict) or not label:
                continue
            opts = {str(k).strip().upper(): str(v).strip() for k, v in options.items()}
            images = row.get("images") or []
            if not isinstance(images, list):
                images = []
            out.append(MedXpertQuestion(
                qid=qid,
                question=question,
                options=opts,
                label=label,
                image_files=[str(x).strip() for x in images if str(x).strip()],
                medical_task=str(row.get("medical_task") or "").strip(),
                body_system=str(row.get("body_system") or "").strip(),
                question_type=str(row.get("question_type") or "").strip(),
                split=split,
            ))
    return out


# ---------------------------------------------------------------------------
# Image archive helpers
# ---------------------------------------------------------------------------


def _ensure_images_extracted(images_zip: Path, images_dir: Path) -> None:
    """Extract images.zip once, tolerantly handle re-runs."""

    marker = images_dir / ".extracted_ok"
    if marker.exists():
        return
    images_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting MedXpertQA images.zip -> %s", images_dir)
    with zipfile.ZipFile(images_zip) as zf:
        zf.extractall(images_dir)
    marker.write_text("ok\n", encoding="utf-8")


def _resolve_image_path(image_filename: str, images_dir: Path) -> Path | None:
    """Find a question's image in the (possibly nested) extract directory.

    The zip layout sometimes nests under ``images/`` and sometimes
    flat — handle both.
    """

    direct = images_dir / image_filename
    if direct.exists():
        return direct
    nested = images_dir / "images" / image_filename
    if nested.exists():
        return nested
    # Last-ditch: glob recursively (slow but correct for unusual layouts).
    matches = list(images_dir.rglob(image_filename))
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------


def _render_question_pdf(
    q: MedXpertQuestion,
    *,
    images_dir: Path,
    pdfs_dir: Path,
) -> tuple[Path, list[str]]:
    """Render one MedXpertQA question into a PDF.

    Layout:
      Title:    MedXpertQA — <qid>  (medical_task / body_system)
      Section 1 (case):       full question text
      Section 1 images:       each image flowable + caption
      Section 2 (options):    A) ... B) ... C) ... D) ... E) ...

    Returns (pdf_path, missing_images) so the caller can warn on
    questions where some image files weren't found.
    """

    out_path = pdfs_dir / f"{q.qid}.pdf"
    images: list[PdfImage] = []
    missing: list[str] = []
    for fname in q.image_files:
        resolved = _resolve_image_path(fname, images_dir)
        if resolved is None:
            missing.append(fname)
            continue
        images.append(PdfImage(path=resolved, caption=f"Image: {fname}", max_width_in=5.5))

    title_meta_parts = []
    if q.medical_task:
        title_meta_parts.append(q.medical_task)
    if q.body_system:
        title_meta_parts.append(q.body_system)
    if q.question_type:
        title_meta_parts.append(q.question_type)
    title_suffix = f" ({' / '.join(title_meta_parts)})" if title_meta_parts else ""

    sections = [
        ("Clinical case", q.question, images),
        ("Answer choices", format_options(q.options), None),
    ]
    render_pdf_with_images(
        title=f"MedXpertQA-MM {q.qid}{title_suffix}",
        sections=sections,
        output_path=out_path,
    )
    return out_path, missing


# ---------------------------------------------------------------------------
# Upload helper
# ---------------------------------------------------------------------------


async def _upload_pdfs(
    ctx: RunContext,
    pdf_paths: Iterable[Path],
    *,
    batch_size: int,
    settings: IngestSettings,
) -> dict[str, int]:
    docs_client = ctx.documents_client()
    name_to_id: dict[str, int] = {}
    pdf_list = list(pdf_paths)
    for batch_start in range(0, len(pdf_list), batch_size):
        batch = pdf_list[batch_start:batch_start + batch_size]
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
                document_ids=result.document_ids,
                timeout_s=1800.0,
            )
            statuses = await docs_client.get_status(
                search_space_id=ctx.search_space_id,
                document_ids=all_ids,
            )
            for s in statuses:
                name_to_id[s.title] = s.document_id
        logger.info(
            "Uploaded MedXpertQA batch %d-%d: %d new, %d duplicate",
            batch_start, batch_start + len(batch),
            len(result.document_ids), len(result.duplicate_document_ids),
        )
    return name_to_id


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_ingest(
    ctx: RunContext,
    *,
    split: str = "test",
    max_questions: int | None = None,
    upload_batch_size: int = 8,
    skip_upload: bool = False,
    include_dev: bool = False,
    settings: IngestSettings | None = None,
) -> None:
    """Ingest MedXpertQA-MM into the medical suite.

    Parameters
    ----------
    split : 'test' (default), 'dev', or 'both'
        Which subset to render + upload.
    max_questions : int | None
        Cap on number of questions ingested (handy for fast iteration).
    upload_batch_size : int
        PDFs per ``fileupload`` call.
    skip_upload : bool
        Render PDFs locally but don't push to SurfSense.
    include_dev : bool
        Convenience: equivalent to ``split='both'``.
    """

    settings = settings or IngestSettings(use_vision_llm=True, processing_mode="basic")
    bench_dir = ctx.benchmark_data_dir()
    images_zip_local = bench_dir / "images.zip"
    images_dir = bench_dir / "images"
    pdfs_dir = bench_dir / "pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    hf_cache = bench_dir / ".hf_cache"
    hf_cache.mkdir(parents=True, exist_ok=True)

    # Step 1: download jsonl(s)
    splits_to_load: list[str] = []
    if split == "both" or include_dev:
        splits_to_load = ["dev", "test"]
    elif split in {"dev", "test"}:
        splits_to_load = [split]
    else:
        raise ValueError(f"Unknown split {split!r}; use 'test' / 'dev' / 'both'")

    questions: list[MedXpertQuestion] = []
    for sp in splits_to_load:
        rel = f"MM/{sp}.jsonl"
        local = _hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=rel,
            repo_type=HF_REPO_TYPE,
            cache_dir=str(hf_cache),
        )
        loaded = _load_jsonl(Path(local), split=sp)
        questions.extend(loaded)
        logger.info("Loaded %d MedXpertQA-MM questions from %s split", len(loaded), sp)

    if max_questions is not None and max_questions > 0:
        questions = questions[:max_questions]
    if not questions:
        raise RuntimeError("No MedXpertQA-MM questions loaded; check the split argument.")

    # Step 2: download images.zip + extract once
    if not images_zip_local.exists():
        local_zip = _hf_hub_download(
            repo_id=HF_REPO_ID,
            filename="images.zip",
            repo_type=HF_REPO_TYPE,
            cache_dir=str(hf_cache),
        )
        # Materialise into bench_dir so the path is stable.
        try:
            from os import link as _link
            _link(local_zip, images_zip_local)
        except OSError:
            from shutil import copy2
            copy2(local_zip, images_zip_local)
    _ensure_images_extracted(images_zip_local, images_dir)

    # Step 3: render PDFs
    pdf_paths: dict[str, Path] = {}
    missing_image_count = 0
    for i, q in enumerate(questions, start=1):
        try:
            pdf, missing = _render_question_pdf(q, images_dir=images_dir, pdfs_dir=pdfs_dir)
            pdf_paths[q.qid] = pdf
            if missing:
                missing_image_count += len(missing)
                logger.debug("qid=%s missing %d images: %s", q.qid, len(missing), missing)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to render MedXpertQA PDF for %s: %s", q.qid, exc)
        if i % 50 == 0:
            logger.info("  ... rendered %d / %d PDFs", i, len(questions))
    if missing_image_count:
        logger.warning(
            "MedXpertQA: %d image references could not be resolved on disk "
            "(rendered PDFs may be missing some images).",
            missing_image_count,
        )

    # Step 4: upload
    name_to_id: dict[str, int] = {}
    if skip_upload:
        logger.info("MedXpertQA: --skip-upload set; skipping SurfSense ingestion")
    else:
        logger.info("MedXpertQA upload settings: %s", settings.render_label())
        name_to_id = await _upload_pdfs(
            ctx,
            pdf_paths.values(),
            batch_size=upload_batch_size,
            settings=settings,
        )

    # Step 5: persist manifest + questions
    questions_jsonl = bench_dir / "questions.jsonl"
    with questions_jsonl.open("w", encoding="utf-8") as fh:
        for q in questions:
            fh.write(json.dumps({
                "qid": q.qid,
                "question": q.question,
                "options": q.options,
                "label": q.label,
                "image_files": q.image_files,
                "medical_task": q.medical_task,
                "body_system": q.body_system,
                "question_type": q.question_type,
                "split": q.split,
            }) + "\n")
    logger.info("Wrote %d MedXpertQA questions to %s", len(questions), questions_jsonl)

    map_path = ctx.maps_dir() / "medxpertqa_doc_map.jsonl"
    with map_path.open("w", encoding="utf-8") as fh:
        # Header line records the resolved ingest settings
        # (see core/ingest_settings.py).
        fh.write(settings_header_line(settings) + "\n")
        for q in questions:
            local = pdf_paths.get(q.qid)
            if local is None:
                continue
            fh.write(json.dumps({
                "qid": q.qid,
                "document_id": name_to_id.get(local.name),
                "pdf_path": str(local),
                "n_images": len(q.image_files),
                "split": q.split,
            }) + "\n")
    logger.info("Wrote MedXpertQA doc map to %s", map_path)

    new_state = ctx.suite_state
    new_state.ingestion_maps["medxpertqa"] = str(map_path)
    set_suite_state(ctx.config, ctx.suite, new_state)


__all__ = ["MedXpertQuestion", "run_ingest"]
