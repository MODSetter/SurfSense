"""Retry only the failed (arm, question) pairs from a previous parser_compare run.

The original parser_compare run records one row per (arm, qid) in
``raw.jsonl``. Some of those rows came back with transient transport
errors (SSL alerts, gateway 502s, empty SSE streams) or empty
``raw_text``. This script re-issues *only* those calls with exponential
backoff so we can see how many recover.

Design constraints / choices:

* **No re-ingest.** All cached PDFs and parser-extracted markdown stay
  on disk. We rebuild ``ArmRequest`` objects from the existing manifest
  + the original ``mmlongbench/questions.jsonl``.
* **No SurfSense backend or celery required.** SurfSense had 0
  reported failures; this script will skip any ``surfsense_agentic``
  rows it encounters and warn rather than try to start the backend.
* **Original ``raw.jsonl`` is never mutated.** Retries land in a
  sibling ``raw_retries.jsonl`` so the original artifact stays
  citeable.
* **Idempotent.** Re-running this script re-tries the same set of
  failed rows from ``raw.jsonl``. If you want to merge survivor rows
  back in, do that as a separate aggregation step.

Usage:

    python scripts/retry_failed_questions.py \
        --run-id 2026-05-14T00-53-19Z \
        --max-attempts 5 \
        --concurrency 2

Outputs (written next to the original raw.jsonl):

* ``raw_retries.jsonl`` — one line per retried (arm, qid). Each line
  carries the original error, every retry attempt's timing/error,
  and the final result (incl. grade) so you can drop it straight
  into a notebook.
* ``raw_retries_summary.json`` — per-arm tried/recovered/still-failed
  counts and an aggregated retry-success rate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dotenv import load_dotenv  # noqa: E402

from surfsense_evals.core.arms import (  # noqa: E402
    ArmRequest,
    ArmResult,
    BareLlmArm,
    NativePdfArm,
)
from surfsense_evals.core.parse.freeform_answer import (  # noqa: E402
    extract_freeform_answer,
)
from surfsense_evals.core.providers.openrouter_chat import (  # noqa: E402
    OpenRouterChatProvider,
)
from surfsense_evals.core.providers.openrouter_pdf import (  # noqa: E402
    OpenRouterPdfProvider,
    PdfEngine,
)
from surfsense_evals.suites.multimodal_doc.mmlongbench.grader import grade  # noqa: E402
from surfsense_evals.suites.multimodal_doc.parser_compare.prompt import (  # noqa: E402
    build_long_context_prompt,
    build_native_pdf_prompt,
)

logger = logging.getLogger("retry_failed_questions")

LC_ARMS = {
    "azure_basic_lc",
    "azure_premium_lc",
    "llamacloud_basic_lc",
    "llamacloud_premium_lc",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_failure_row(row: dict[str, Any]) -> bool:
    """A row counts as failed if it raised an error OR returned empty text.

    We retry both because the empty-stream case is the same operational
    failure mode (the call returned nothing usable) — we just didn't
    raise it as an exception.
    """

    if row.get("error"):
        return True
    return bool(not (row.get("raw_text") or "").strip())


@dataclass
class FailedRow:
    arm: str
    qid: str
    doc_id: str
    answer_format: str
    gold: str
    pages: int
    document_id: int | None
    original_error: str | None
    original_row: dict[str, Any]


def _load_failed_rows(raw_path: Path) -> list[FailedRow]:
    out: list[FailedRow] = []
    with raw_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not _is_failure_row(row):
                continue
            out.append(
                FailedRow(
                    arm=str(row["arm"]),
                    qid=str(row["qid"]),
                    doc_id=str(row["doc_id"]),
                    answer_format=str(row.get("answer_format") or ""),
                    gold=str(row.get("gold") or ""),
                    pages=int(row.get("pages") or 0),
                    document_id=row.get("document_id"),
                    original_error=row.get("error"),
                    original_row=row,
                )
            )
    return out


def _load_doc_map(map_path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with map_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out[str(row["doc_id"])] = row
    return out


def _load_question_text_index(
    questions_jsonl: Path,
) -> dict[tuple[str, int], dict[str, Any]]:
    """Map (doc_id, per_doc_index) -> raw question row.

    qids in raw.jsonl are formatted ``{doc_id}::Q{NNN}`` where NNN is
    the per-doc index. Reproducing the runner's question selection
    requires walking ``questions.jsonl`` in order and assigning
    indices per doc_id (so we match the runner's ``per_doc_idx`` logic
    in ``_select_questions``).
    """

    out: dict[tuple[str, int], dict[str, Any]] = {}
    per_doc_idx: dict[str, int] = {}
    with questions_jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            doc_id = str(row.get("doc_id") or "")
            if not doc_id:
                continue
            idx = per_doc_idx.get(doc_id, 0)
            per_doc_idx[doc_id] = idx + 1
            out[(doc_id, idx)] = row
    return out


def _qid_index(qid: str) -> int:
    """Parse the per-doc question index out of a qid like ``foo.pdf::Q007``."""

    _, _, q_part = qid.rpartition("::")
    if not q_part.startswith("Q"):
        raise ValueError(f"unexpected qid shape: {qid!r}")
    return int(q_part[1:])


# ---------------------------------------------------------------------------
# Request building (mirrors runner.py exactly so prompts are byte-identical)
# ---------------------------------------------------------------------------


def _build_native_request(
    qid: str,
    question: str,
    answer_format: str,
    pdf_path: Path,
    *,
    max_output_tokens: int,
) -> ArmRequest:
    return ArmRequest(
        question_id=qid,
        prompt=build_native_pdf_prompt(question, answer_format=answer_format),
        pdf_paths=[pdf_path],
        options={"max_tokens": max_output_tokens},
    )


def _build_lc_request(
    qid: str,
    question: str,
    answer_format: str,
    doc_id: str,
    md_path: Path,
) -> ArmRequest:
    if not md_path.exists():
        raise FileNotFoundError(f"Missing parser extraction at {md_path}; cannot retry LC arm.")
    markdown = md_path.read_text(encoding="utf-8")
    return ArmRequest(
        question_id=qid,
        prompt=build_long_context_prompt(
            question,
            answer_format=answer_format,
            document_markdown=markdown,
            document_label=doc_id,
        ),
    )


# ---------------------------------------------------------------------------
# Retry driver
# ---------------------------------------------------------------------------


@dataclass
class AttemptLog:
    attempt: int
    started_iso: str
    latency_ms: int
    error: str | None
    raw_text_chars: int


@dataclass
class RetryOutcome:
    arm: str
    qid: str
    attempts: list[AttemptLog]
    final_result: ArmResult
    recovered: bool


async def _retry_one(
    arm_obj: Any,
    request: ArmRequest,
    *,
    arm_name: str,
    qid: str,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
) -> RetryOutcome:
    attempts: list[AttemptLog] = []
    final: ArmResult | None = None
    for attempt in range(1, max_attempts + 1):
        started_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        t0 = time.monotonic()
        result = await arm_obj.answer(request)
        latency_ms = int((time.monotonic() - t0) * 1000)
        raw_text = (result.raw_text or "").strip()
        attempt_error = result.error
        if not attempt_error and not raw_text:
            attempt_error = "EmptyResponse: stream ended with no text"
        attempts.append(
            AttemptLog(
                attempt=attempt,
                started_iso=started_iso,
                latency_ms=latency_ms,
                error=attempt_error,
                raw_text_chars=len(raw_text),
            )
        )
        final = result
        if not attempt_error and raw_text:
            return RetryOutcome(
                arm=arm_name,
                qid=qid,
                attempts=attempts,
                final_result=result,
                recovered=True,
            )
        if attempt < max_attempts:
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay * (0.5 + random.random())
            logger.info(
                "[%s::%s] attempt %d/%d failed (%s); sleeping %.1fs",
                arm_name,
                qid,
                attempt,
                max_attempts,
                attempt_error,
                delay,
            )
            await asyncio.sleep(delay)
    assert final is not None
    return RetryOutcome(
        arm=arm_name,
        qid=qid,
        attempts=attempts,
        final_result=final,
        recovered=False,
    )


async def _gather_with_limit(coros: list, *, concurrency: int) -> list[Any]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _wrap(coro):
        async with sem:
            return await coro

    return await asyncio.gather(*(_wrap(c) for c in coros))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> int:
    load_dotenv(REPO / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    run_dir = REPO / "data" / "multimodal_doc" / "runs" / args.run_id / "parser_compare"
    raw_path = run_dir / "raw.jsonl"
    if not raw_path.exists():
        raise SystemExit(f"raw.jsonl not found at {raw_path}")

    map_path = REPO / "data" / "multimodal_doc" / "maps" / "parser_compare_doc_map.jsonl"
    questions_jsonl = REPO / "data" / "multimodal_doc" / "mmlongbench" / "questions.jsonl"
    if not map_path.exists():
        raise SystemExit(f"parser_compare manifest not found at {map_path}")
    if not questions_jsonl.exists():
        raise SystemExit(f"mmlongbench questions not found at {questions_jsonl}")

    failed = _load_failed_rows(raw_path)
    if not failed:
        logger.info("No failed rows in %s — nothing to retry.", raw_path)
        return 0

    # SurfSense rows: warn and skip; we don't want to start backend just to
    # defensively retry a 0-failure arm.
    surf_failed = [f for f in failed if f.arm == "surfsense_agentic"]
    if surf_failed:
        logger.warning(
            "Skipping %d surfsense_agentic failures; this script doesn't drive the backend. "
            "If you want those retried too, start backend + celery and rerun "
            "with --include-surfsense.",
            len(surf_failed),
        )
        if not args.include_surfsense:
            failed = [f for f in failed if f.arm != "surfsense_agentic"]
    else:
        logger.info("No surfsense_agentic failures; backend/celery not needed for this retry.")

    if not failed:
        logger.info("Nothing left to retry after filtering.")
        return 0

    by_arm_count: dict[str, int] = {}
    for f in failed:
        by_arm_count[f.arm] = by_arm_count.get(f.arm, 0) + 1
    logger.info(
        "Loaded %d failed rows across %d arms: %s",
        len(failed),
        len(by_arm_count),
        ", ".join(f"{a}={n}" for a, n in sorted(by_arm_count.items())),
    )

    doc_map = _load_doc_map(map_path)
    qtext_idx = _load_question_text_index(questions_jsonl)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY missing from environment / .env")

    native_provider = OpenRouterPdfProvider(
        api_key=api_key,
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        model=args.llm_model,
        engine=PdfEngine(args.pdf_engine),
    )
    native_arm = NativePdfArm(
        provider=native_provider,
        max_output_tokens=args.max_output_tokens,
    )

    lc_arms: dict[str, BareLlmArm] = {}
    for arm_name in sorted({f.arm for f in failed} & LC_ARMS):
        lc_provider = OpenRouterChatProvider(
            api_key=api_key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=args.llm_model,
        )
        lc_arms[arm_name] = BareLlmArm(
            provider=lc_provider,
            max_output_tokens=args.max_output_tokens,
            name=arm_name,
        )

    coros: list = []
    plan: list[tuple[FailedRow, ArmRequest, Any]] = []

    for f in failed:
        # Look up the question text from questions.jsonl
        try:
            q_idx = _qid_index(f.qid)
        except Exception:
            logger.error("Bad qid %r — skipping", f.qid)
            continue
        qrow = qtext_idx.get((f.doc_id, q_idx))
        if qrow is None:
            logger.error(
                "Could not find question text for %s (idx %d) — skipping",
                f.doc_id,
                q_idx,
            )
            continue
        question_text = str(qrow.get("question") or "").strip()
        answer_format = str(qrow.get("answer_format") or f.answer_format or "").strip().lower()

        map_row = doc_map.get(f.doc_id)
        if map_row is None:
            logger.error("doc_id %s not in manifest — skipping", f.doc_id)
            continue

        if f.arm == "native_pdf":
            pdf_path = Path(map_row["pdf_path"])
            if not await asyncio.to_thread(pdf_path.exists):
                logger.error("PDF missing on disk: %s — skipping", pdf_path)
                continue
            request = _build_native_request(
                f.qid,
                question_text,
                answer_format,
                pdf_path,
                max_output_tokens=args.max_output_tokens,
            )
            arm_obj = native_arm
        elif f.arm in LC_ARMS:
            ext_blob = (map_row.get("extractions") or {}).get(f.arm) or {}
            md_path_str = ext_blob.get("markdown_path")
            if not md_path_str or ext_blob.get("status") != "ok":
                logger.error(
                    "Missing extraction for %s on %s — cannot retry; skipping",
                    f.arm,
                    f.doc_id,
                )
                continue
            request = _build_lc_request(
                f.qid,
                question_text,
                answer_format,
                f.doc_id,
                Path(md_path_str),
            )
            arm_obj = lc_arms[f.arm]
        else:
            logger.warning("Unhandled arm %s — skipping", f.arm)
            continue

        plan.append((f, request, arm_obj))
        coros.append(
            _retry_one(
                arm_obj,
                request,
                arm_name=f.arm,
                qid=f.qid,
                max_attempts=args.max_attempts,
                base_delay=args.base_delay,
                max_delay=args.max_delay,
            )
        )

    if not coros:
        logger.warning("Nothing to retry after request building.")
        return 0

    logger.info(
        "Retrying %d failed rows with up to %d attempts each "
        "(base_delay=%.1fs, max_delay=%.1fs, concurrency=%d).",
        len(coros),
        args.max_attempts,
        args.base_delay,
        args.max_delay,
        args.concurrency,
    )

    started = time.monotonic()
    outcomes: list[RetryOutcome] = await _gather_with_limit(
        coros,
        concurrency=args.concurrency,
    )
    elapsed = time.monotonic() - started
    logger.info("Retry pass finished in %.1fs.", elapsed)

    out_path = run_dir / "raw_retries.jsonl"
    summary_path = run_dir / "raw_retries_summary.json"

    per_arm_recovered: dict[str, int] = {}
    per_arm_total: dict[str, int] = {}
    per_arm_attempts_dist: dict[str, list[int]] = {}

    with out_path.open("w", encoding="utf-8") as fh:
        for (f, _req, _arm_obj), outcome in zip(plan, outcomes, strict=True):
            per_arm_total[outcome.arm] = per_arm_total.get(outcome.arm, 0) + 1
            if outcome.recovered:
                per_arm_recovered[outcome.arm] = per_arm_recovered.get(outcome.arm, 0) + 1
            per_arm_attempts_dist.setdefault(outcome.arm, []).append(len(outcome.attempts))

            g = grade(
                pred=extract_freeform_answer(outcome.final_result.raw_text or ""),
                gold=f.gold,
                answer_format=f.answer_format,
            )
            row = {
                "qid": f.qid,
                "doc_id": f.doc_id,
                "arm": f.arm,
                "answer_format": f.answer_format,
                "gold": f.gold,
                "pages": f.pages,
                "document_id": f.document_id,
                "original_error": f.original_error,
                "retry": {
                    "max_attempts": args.max_attempts,
                    "n_attempts": len(outcome.attempts),
                    "recovered": outcome.recovered,
                    "attempts": [
                        {
                            "attempt": a.attempt,
                            "started_iso": a.started_iso,
                            "latency_ms": a.latency_ms,
                            "error": a.error,
                            "raw_text_chars": a.raw_text_chars,
                        }
                        for a in outcome.attempts
                    ],
                },
                **outcome.final_result.to_jsonl(),
                "graded": {
                    "correct": g.correct,
                    "f1": g.f1,
                    "method": g.method,
                    "normalised_pred": g.normalised_pred,
                    "normalised_gold": g.normalised_gold,
                },
            }
            fh.write(json.dumps(row) + "\n")

    summary = {
        "run_id": args.run_id,
        "raw_retries_path": str(out_path.relative_to(REPO)),
        "n_failed_rows_input": len(failed),
        "n_retried": len(coros),
        "elapsed_s": round(elapsed, 1),
        "config": {
            "max_attempts": args.max_attempts,
            "base_delay": args.base_delay,
            "max_delay": args.max_delay,
            "concurrency": args.concurrency,
            "llm_model": args.llm_model,
            "pdf_engine": args.pdf_engine,
            "max_output_tokens": args.max_output_tokens,
        },
        "per_arm": {
            arm: {
                "tried": per_arm_total.get(arm, 0),
                "recovered": per_arm_recovered.get(arm, 0),
                "still_failed": (per_arm_total.get(arm, 0) - per_arm_recovered.get(arm, 0)),
                "recovery_rate": (
                    per_arm_recovered.get(arm, 0) / per_arm_total[arm]
                    if per_arm_total.get(arm)
                    else 0.0
                ),
                "attempts_distribution": sorted(per_arm_attempts_dist.get(arm, [])),
            }
            for arm in sorted(per_arm_total)
        },
        "totals": {
            "tried": sum(per_arm_total.values()),
            "recovered": sum(per_arm_recovered.values()),
            "still_failed": sum(per_arm_total.values()) - sum(per_arm_recovered.values()),
        },
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 78)
    print("Retry pass summary")
    print("=" * 78)
    header = f"{'arm':<25} {'tried':>6} {'recovered':>10} {'still fail':>11} {'rate':>7}"
    print(header)
    print("-" * len(header))
    for arm in sorted(per_arm_total):
        tried = per_arm_total[arm]
        rec = per_arm_recovered.get(arm, 0)
        rate = (rec / tried * 100) if tried else 0.0
        print(f"{arm:<25} {tried:>6} {rec:>10} {tried - rec:>11} {rate:>6.1f}%")
    total = sum(per_arm_total.values())
    rec_total = sum(per_arm_recovered.values())
    rate_total = (rec_total / total * 100) if total else 0.0
    print("-" * len(header))
    print(f"{'TOTAL':<25} {total:>6} {rec_total:>10} {total - rec_total:>11} {rate_total:>6.1f}%")
    print()
    print(f"Wrote {out_path.relative_to(REPO)}")
    print(f"Wrote {summary_path.relative_to(REPO)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-id",
        default="2026-05-14T00-53-19Z",
        help="Run timestamp under data/multimodal_doc/runs/. Default is the "
        "n=171 production run we wrote up in the blog.",
    )
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument(
        "--base-delay",
        type=float,
        default=1.0,
        help="Base seconds for exponential backoff (default 1s).",
    )
    parser.add_argument(
        "--max-delay", type=float, default=30.0, help="Cap on per-retry sleep (default 30s)."
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Parallel retries in flight (default 2 — keep low "
        "to avoid the same transport stress that caused "
        "the original failures).",
    )
    parser.add_argument("--llm-model", default="anthropic/claude-sonnet-4.5")
    parser.add_argument("--pdf-engine", default="native", choices=[e.value for e in PdfEngine])
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument(
        "--include-surfsense",
        action="store_true",
        help="Also retry surfsense_agentic failures (requires backend + celery up). "
        "Default is to skip them since the n=171 run had 0 SurfSense failures.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
