"""parser_compare runner — six-arm head-to-head on n shared questions.

For each (PDF, question) pair we issue six LLM calls (all sonnet 4.5):

* ``native_pdf``           — PDF attached natively.
* ``azure_basic_lc``       — Azure prebuilt-read markdown stuffed.
* ``azure_premium_lc``     — Azure prebuilt-layout markdown stuffed.
* ``llamacloud_basic_lc``  — LlamaParse parse_page_with_llm markdown stuffed.
* ``llamacloud_premium_lc`` — LlamaParse parse_page_with_agent markdown stuffed.
* ``surfsense_agentic``    — SurfSense /api/v1/new_chat retrieval over chunks.

Cost reporting:

* ``llm_cost_per_q``       — mean OpenRouter ``usage.cost`` reported by
                              the chat-completions API. Zero for the
                              SurfSense agentic arm because the SSE
                              stream doesn't surface per-call cost yet
                              (a known gap; we annotate it in the
                              report rather than estimating).
* ``preprocess_cost_total`` — pages * $/1k according to the user's
                              tariff:
                                * basic   : $1   / 1k pages
                                * premium : $10  / 1k pages
                                * native_pdf : $0  (no preprocessing)
                                * surfsense_agentic : $10 / 1k pages
                                  (existing mmlongbench ingest used
                                  processing_mode=premium with Azure DI).
* ``preprocess_cost_per_q`` — preprocess_cost_total / n_questions.
* ``total_cost_per_q``      — llm_cost_per_q + preprocess_cost_per_q.

The grader is reused from ``mmlongbench/grader.py`` (deterministic,
format-aware) so the metric is directly comparable to the existing
mmlongbench runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....core.arms import (
    ArmRequest,
    ArmResult,
    BareLlmArm,
    NativePdfArm,
    SurfSenseArm,
)
from ....core.config import utc_iso_timestamp
from ....core.metrics.mc_accuracy import accuracy_with_wilson_ci
from ....core.parse.freeform_answer import extract_freeform_answer
from ....core.providers.openrouter_chat import OpenRouterChatProvider
from ....core.providers.openrouter_pdf import OpenRouterPdfProvider, PdfEngine
from ....core.registry import ReportSection, RunArtifact, RunContext
from ..mmlongbench.grader import GradeResult, grade
from .ingest import PARSER_ARMS
from .prompt import (
    build_long_context_prompt,
    build_native_pdf_prompt,
    build_surfsense_prompt,
)

logger = logging.getLogger(__name__)


# Cost tariff (per the user's spec: $1 / 1k pages basic, $10 / 1k pages premium).
# Held as dollars-per-page so per-PDF math is a pure multiply.
PREPROCESS_USD_PER_PAGE = {
    "basic":   1.0  / 1000.0,
    "premium": 10.0 / 1000.0,
}

ARM_NAMES = (
    "native_pdf",
    "azure_basic_lc",
    "azure_premium_lc",
    "llamacloud_basic_lc",
    "llamacloud_premium_lc",
    "surfsense_agentic",
)

# What ingest mode each LC arm corresponds to (drives preprocess cost).
_LC_ARM_MODE: dict[str, str] = {
    "azure_basic_lc": "basic",
    "azure_premium_lc": "premium",
    "llamacloud_basic_lc": "basic",
    "llamacloud_premium_lc": "premium",
}

# The SurfSense agentic arm is fed by the existing mmlongbench
# ingestion. That ingestion was performed with vision_llm=on and
# processing_mode=premium, and the backend's ETL routes premium-mode
# PDFs through Azure DI prebuilt-layout when AZURE_DI_KEY is set. So
# the preprocessing cost is the premium tariff.
SURFSENSE_INGEST_MODE = "premium"


# ---------------------------------------------------------------------------
# Question + PDF row shapes
# ---------------------------------------------------------------------------


@dataclass
class PCQuestion:
    qid: str
    doc_id: str
    question: str
    gold_answer: str
    answer_format: str
    pdf_path: Path
    document_id: int | None
    pages: int
    extractions: dict[str, Path]  # arm_name -> markdown path (only successes)


def _read_doc_map(map_path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with map_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out[str(row["doc_id"])] = row
    return out


def _select_questions(
    questions_jsonl: Path,
    doc_map: dict[str, dict[str, Any]],
    *,
    docs_filter: list[str] | None,
    sample_per_doc: int,
    skip_unanswerable: bool,
    skip_format: list[str] | None,
) -> list[PCQuestion]:
    """Pick the first ``sample_per_doc`` questions per PDF in scope.

    Defaults to one per PDF (n=5 across 5 PDFs ⇒ 5 questions). Filters
    out unanswerable probes by default since they're noise at small n.
    """

    out: list[PCQuestion] = []
    per_doc_taken: dict[str, int] = {}
    per_doc_idx: dict[str, int] = {}
    skip_format_set = {f.lower() for f in (skip_format or [])}

    with questions_jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            doc_id = str(row.get("doc_id") or "")
            if not doc_id:
                continue
            if docs_filter and doc_id not in docs_filter:
                continue
            map_row = doc_map.get(doc_id)
            if map_row is None:
                continue

            answer_format = str(row.get("answer_format") or "").strip().lower()
            idx = per_doc_idx.get(doc_id, 0)
            per_doc_idx[doc_id] = idx + 1

            if skip_unanswerable and answer_format == "none":
                continue
            if answer_format in skip_format_set:
                continue

            if per_doc_taken.get(doc_id, 0) >= sample_per_doc:
                continue

            extractions: dict[str, Path] = {}
            for arm_name, ext_blob in (map_row.get("extractions") or {}).items():
                if ext_blob.get("status") == "ok" and ext_blob.get("markdown_path"):
                    extractions[arm_name] = Path(ext_blob["markdown_path"])

            out.append(PCQuestion(
                qid=f"{doc_id}::Q{idx:03d}",
                doc_id=doc_id,
                question=str(row.get("question") or "").strip(),
                gold_answer=str(row.get("answer") or "").strip(),
                answer_format=answer_format,
                pdf_path=Path(map_row["pdf_path"]),
                document_id=map_row.get("document_id"),
                pages=int(map_row.get("pages", 0)),
                extractions=extractions,
            ))
            per_doc_taken[doc_id] = per_doc_taken.get(doc_id, 0) + 1

    out.sort(key=lambda q: (q.doc_id, q.qid))
    return out


# ---------------------------------------------------------------------------
# Bounded concurrency helper
# ---------------------------------------------------------------------------


async def _gather_with_limit(coros: Iterable, *, concurrency: int) -> list[Any]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _wrap(coro):
        async with sem:
            return await coro

    return await asyncio.gather(*(_wrap(c) for c in coros))


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


_DESCRIPTION = (
    "parser_compare — 6-arm head-to-head on shared MMLongBench-Doc PDFs: "
    "native PDF + (Azure DI / LlamaCloud) x (basic / premium) long-context "
    "stuffing + SurfSense agentic retrieval. Reports preprocessing dollars "
    "($1 / 1k pages basic, $10 / 1k pages premium) on top of LLM cost."
)


class ParserCompareBenchmark:
    """6-arm parser + agentic-vs-non-agentic head-to-head."""

    suite: str = "multimodal_doc"
    name: str = "parser_compare"
    headline: bool = True
    description: str = _DESCRIPTION

    # ------------------------------------------------------------------
    # CLI flags
    # ------------------------------------------------------------------

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--docs", default=None,
            help="Comma-separated doc_ids to include (default: all in manifest).",
        )
        parser.add_argument(
            "--sample-per-doc", type=int, default=1,
            help="Take the first N answerable questions per PDF (default 1).",
        )
        parser.add_argument(
            "--skip-unanswerable", dest="skip_unanswerable",
            action="store_true", default=True,
            help="Drop 'None' format probes (default true; we want signal not "
                 "hallucination probes for n=5).",
        )
        parser.add_argument(
            "--include-unanswerable", dest="skip_unanswerable",
            action="store_false",
            help="Override --skip-unanswerable; include unanswerable probes too.",
        )
        parser.add_argument(
            "--skip-format", default=None,
            help="Comma-separated answer_format values to skip (e.g. 'none,float').",
        )
        parser.add_argument(
            "--concurrency", type=int, default=2,
            help="Parallel question workers per arm (default 2).",
        )
        parser.add_argument(
            "--no-mentions", dest="no_mentions", action="store_true",
            help="SurfSense arm: skip mentioned_document_ids (full-corpus retrieval).",
        )
        parser.add_argument(
            "--pdf-engine", default="native",
            choices=[e.value for e in PdfEngine],
            help="OpenRouter file-parser engine for native_pdf arm.",
        )
        parser.add_argument(
            "--max-output-tokens", type=int, default=512,
            help="Cap on completion length for every arm.",
        )
        parser.add_argument(
            "--llm-model", default="anthropic/claude-sonnet-4.5",
            help="OpenRouter slug used by the 5 OpenRouter-driven arms. "
                 "SurfSense arm uses whatever provider_model is pinned on the suite.",
        )
        parser.add_argument(
            "--skip-arms", default=None,
            help="Comma-separated arm names to skip (e.g. 'llamacloud_premium_lc').",
        )
        # Ingest-only flags (forwarded by the CLI to ingest.run_ingest).
        parser.add_argument(
            "--max-docs", type=int, default=None,
            help="(ingest only) cap number of unique PDFs to process.",
        )
        parser.add_argument(
            "--force-reextract", action="store_true",
            help="(ingest only) re-call parsers even if cached .md exists.",
        )
        parser.add_argument(
            "--pdf-concurrency", type=int, default=2,
            help="(ingest only) parallel PDFs (each fans out to 4 parsers).",
        )

    # ------------------------------------------------------------------
    # Lifecycle: ingest delegates to .ingest.run_ingest
    # ------------------------------------------------------------------

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import run_ingest

        docs_raw: str | None = opts.get("docs")
        docs_filter = (
            [d.strip() for d in docs_raw.split(",") if d.strip()] if docs_raw else None
        )
        await run_ingest(
            ctx,
            docs_filter=docs_filter,
            max_docs=opts.get("max_docs"),
            force_reextract=bool(opts.get("force_reextract", False)),
            pdf_concurrency=int(opts.get("pdf_concurrency") or 2),
        )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        docs_raw: str | None = opts.get("docs")
        docs_filter = (
            [d.strip() for d in docs_raw.split(",") if d.strip()] if docs_raw else None
        )
        sample_per_doc = int(opts.get("sample_per_doc") or 1)
        skip_unanswerable = bool(opts.get("skip_unanswerable", True))
        skip_format_raw: str | None = opts.get("skip_format")
        skip_format = (
            [f.strip() for f in skip_format_raw.split(",") if f.strip()]
            if skip_format_raw else None
        )
        concurrency = int(opts.get("concurrency") or 2)
        no_mentions = bool(opts.get("no_mentions"))
        pdf_engine_name = opts.get("pdf_engine") or "native"
        max_output_tokens = int(opts.get("max_output_tokens") or 512)
        llm_model = str(opts.get("llm_model") or "anthropic/claude-sonnet-4.5")
        skip_arms_raw: str | None = opts.get("skip_arms")
        skip_arms = (
            {a.strip() for a in skip_arms_raw.split(",") if a.strip()}
            if skip_arms_raw else set()
        )

        active_arms = [a for a in ARM_NAMES if a not in skip_arms]
        if not active_arms:
            raise RuntimeError("All arms skipped; nothing to run.")

        bench_dir = ctx.benchmark_data_dir()
        # parser_compare reuses mmlongbench's questions.jsonl (already
        # downloaded by `ingest multimodal_doc mmlongbench`).
        questions_jsonl = bench_dir.parent / "mmlongbench" / "questions.jsonl"
        map_path = ctx.maps_dir() / "parser_compare_doc_map.jsonl"
        if not questions_jsonl.exists():
            raise RuntimeError(
                "Missing mmlongbench questions at "
                f"{questions_jsonl}. Run "
                "`python -m surfsense_evals ingest multimodal_doc mmlongbench` first."
            )
        if not map_path.exists():
            raise RuntimeError(
                "parser_compare doc map missing. Run "
                "`python -m surfsense_evals ingest multimodal_doc parser_compare` first."
            )

        doc_map = _read_doc_map(map_path)
        questions = _select_questions(
            questions_jsonl, doc_map,
            docs_filter=docs_filter,
            sample_per_doc=sample_per_doc,
            skip_unanswerable=skip_unanswerable,
            skip_format=skip_format,
        )
        if not questions:
            raise RuntimeError(
                "No questions matched filters; broaden --docs / --skip-format."
            )
        logger.info(
            "parser_compare: scheduled %d questions across %d arms (%s)",
            len(questions), len(active_arms), ",".join(active_arms),
        )

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY env var is required.")

        # Build arms
        arms: dict[str, Any] = {}
        if "native_pdf" in active_arms:
            native_provider = OpenRouterPdfProvider(
                api_key=api_key, base_url=ctx.config.openrouter_base_url,
                model=llm_model, engine=PdfEngine(pdf_engine_name),
            )
            arms["native_pdf"] = NativePdfArm(
                provider=native_provider, max_output_tokens=max_output_tokens,
            )
        for arm_name, _, _ in PARSER_ARMS:
            if arm_name in active_arms:
                lc_provider = OpenRouterChatProvider(
                    api_key=api_key, base_url=ctx.config.openrouter_base_url,
                    model=llm_model,
                )
                arms[arm_name] = BareLlmArm(
                    provider=lc_provider,
                    max_output_tokens=max_output_tokens,
                    name=arm_name,
                )
        if "surfsense_agentic" in active_arms:
            surf = SurfSenseArm(
                client=ctx.new_chat_client(),
                search_space_id=ctx.search_space_id,
                ephemeral_threads=True,
            )
            # Override the default "surfsense" name so the metrics
            # bucket lines up with the rest of parser_compare's arms.
            surf.name = "surfsense_agentic"
            arms["surfsense_agentic"] = surf

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"

        # ---- per-arm answer coroutine helpers ----

        def _native_req(q: PCQuestion) -> ArmRequest:
            return ArmRequest(
                question_id=q.qid,
                prompt=build_native_pdf_prompt(q.question, answer_format=q.answer_format),
                pdf_paths=[q.pdf_path],
                options={"max_tokens": max_output_tokens},
            )

        def _lc_req(q: PCQuestion, arm_name: str) -> ArmRequest:
            md_path = q.extractions.get(arm_name)
            if md_path is None or not md_path.exists():
                raise FileNotFoundError(
                    f"Missing extraction for {arm_name} on {q.doc_id}"
                )
            markdown = md_path.read_text(encoding="utf-8")
            return ArmRequest(
                question_id=q.qid,
                prompt=build_long_context_prompt(
                    q.question,
                    answer_format=q.answer_format,
                    document_markdown=markdown,
                    document_label=q.doc_id,
                ),
            )

        def _surf_req(q: PCQuestion) -> ArmRequest:
            mentions: list[int] | None = None
            if not no_mentions and q.document_id is not None:
                mentions = [int(q.document_id)]
            return ArmRequest(
                question_id=q.qid,
                prompt=build_surfsense_prompt(q.question, answer_format=q.answer_format),
                mentioned_document_ids=mentions,
            )

        async def _answer_one(arm_name: str, q: PCQuestion) -> ArmResult:
            arm = arms[arm_name]
            try:
                if arm_name == "native_pdf":
                    return await arm.answer(_native_req(q))
                if arm_name == "surfsense_agentic":
                    return await arm.answer(_surf_req(q))
                return await arm.answer(_lc_req(q, arm_name))
            except FileNotFoundError as exc:
                return ArmResult(
                    arm=arm_name,
                    question_id=q.qid,
                    raw_text="",
                    error=f"FileNotFoundError: {exc}",
                )

        # Run all arms in parallel (each arm bounded by `concurrency`).
        per_arm_tasks: dict[str, list] = {
            arm_name: [_answer_one(arm_name, q) for q in questions]
            for arm_name in active_arms
        }
        per_arm_results: dict[str, list[ArmResult]] = {}
        gathered = await asyncio.gather(*[
            _gather_with_limit(per_arm_tasks[arm_name], concurrency=concurrency)
            for arm_name in active_arms
        ])
        for arm_name, results in zip(active_arms, gathered, strict=True):
            per_arm_results[arm_name] = results

        # Grade
        per_arm_grades: dict[str, list[GradeResult]] = {}
        for arm_name in active_arms:
            per_arm_grades[arm_name] = [
                grade(
                    pred=extract_freeform_answer(r.raw_text or ""),
                    gold=q.gold_answer,
                    answer_format=q.answer_format,
                )
                for q, r in zip(questions, per_arm_results[arm_name], strict=True)
            ]

        # Persist raw.jsonl
        with raw_path.open("w", encoding="utf-8") as fh:
            for i, q in enumerate(questions):
                base = {
                    "qid": q.qid,
                    "doc_id": q.doc_id,
                    "answer_format": q.answer_format,
                    "gold": q.gold_answer,
                    "pages": q.pages,
                    "document_id": q.document_id,
                }
                for arm_name in active_arms:
                    res = per_arm_results[arm_name][i]
                    g = per_arm_grades[arm_name][i]
                    fh.write(json.dumps({
                        **base,
                        **res.to_jsonl(),
                        "graded": {
                            "correct": g.correct,
                            "f1": g.f1,
                            "method": g.method,
                            "normalised_pred": g.normalised_pred,
                            "normalised_gold": g.normalised_gold,
                        },
                    }) + "\n")

        # Aggregate per-arm metrics + cost
        metrics = _compute_metrics(
            questions, per_arm_results, per_arm_grades, active_arms,
        )

        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_questions": len(questions),
                "n_pdfs": len({q.doc_id for q in questions}),
                "active_arms": list(active_arms),
                "concurrency": concurrency,
                "no_mentions": no_mentions,
                "pdf_engine": pdf_engine_name,
                "llm_model": llm_model,
                "scenario": ctx.scenario,
                "provider_model": ctx.provider_model,
                "vision_provider_model": ctx.vision_provider_model,
                "agent_llm_id": ctx.agent_llm_id,
                "preprocess_tariff": {
                    "basic_per_1k_pages": 1.0,
                    "premium_per_1k_pages": 10.0,
                },
            },
        )

        manifest_path = run_dir / "run_artifact.json"
        manifest_path.write_text(
            json.dumps({
                "suite": self.suite,
                "benchmark": self.name,
                "raw_path": "raw.jsonl",
                "metrics": metrics,
                "extra": artifact.extra,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="Parser × agent-vs-stuffing comparison",
                headline=True,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        extra = latest.extra
        per_arm = m.get("per_arm", {})
        active_arms = list(extra.get("active_arms", per_arm.keys()))

        n_q = extra.get("n_questions", "?")
        n_pdfs = extra.get("n_pdfs", "?")

        body: list[str] = []
        body.append(
            f"- Sample size: **{n_q} questions across {n_pdfs} PDFs** "
            f"(LLM: `{extra.get('llm_model', '?')}`, "
            f"engine: `{extra.get('pdf_engine', 'native')}`)."
        )
        body.append(
            f"- Preprocess tariff: basic = $1 / 1k pages, "
            f"premium = $10 / 1k pages."
        )
        body.append("")
        body.append("### Per-arm summary")
        body.append("")
        body.append(
            "| Arm | Accuracy | F1 mean | LLM $/Q | Preprocess $ total | Total $/Q | Latency p50 |"
        )
        body.append("|---|---:|---:|---:|---:|---:|---:|")
        for arm_name in active_arms:
            row = per_arm.get(arm_name)
            if not row:
                body.append(f"| `{arm_name}` | (no data) | | | | | |")
                continue
            body.append(
                f"| `{arm_name}` "
                f"| {row['accuracy']*100:.1f}% "
                f"({row['n_correct']}/{row['n']}) "
                f"| {row['f1_mean']*100:.1f}% "
                f"| ${row['llm_cost_per_q']:.4f} "
                f"| ${row['preprocess_cost_total']:.4f} "
                f"| ${row['total_cost_per_q']:.4f} "
                f"| {row['latency_ms_median']/1000:.1f}s |"
            )
        body.append("")

        # Notes / caveats
        body.append("### Notes")
        body.append("")
        body.append(
            "- `surfsense_agentic` LLM cost shows as $0.0000 because the "
            "`/api/v1/new_chat` SSE stream does not surface per-call token "
            "or cost yet (a known instrumentation gap). Preprocessing cost "
            "is the premium tariff because the underlying mmlongbench "
            "ingestion was performed with `processing_mode=premium` + "
            "`vision_llm=on` + Azure DI."
        )
        body.append(
            "- Long-context arms include the **same PDF text** for every "
            "question against that PDF, so the OpenRouter input cost is "
            "dominated by markdown size; preprocessing cost is paid once "
            "across all questions sharing a PDF."
        )
        body.append(
            "- Preprocessing $ total is computed as "
            "`pages_processed_per_arm × tariff`, summed across the unique "
            "PDFs in scope. With one question per PDF (n=5), preprocess $ "
            "= preprocess $ / Q."
        )
        if extra.get("scenario"):
            body.append(
                f"- Scenario: `{extra.get('scenario')}` "
                f"(suite-pinned `provider_model`: "
                f"`{extra.get('provider_model', '?')}`)."
            )

        # Per-PDF breakdown if useful
        per_pdf = m.get("per_pdf", {})
        if per_pdf:
            body.append("")
            body.append("### Per-PDF correctness")
            body.append("")
            header = "| Doc | Pages | " + " | ".join(f"`{a}`" for a in active_arms) + " |"
            sep = "|---|---:|" + "|".join(":---:" for _ in active_arms) + "|"
            body.append(header)
            body.append(sep)
            for doc_id, info in sorted(per_pdf.items()):
                row_cells = []
                for arm_name in active_arms:
                    g = info.get("arms", {}).get(arm_name, {})
                    if not g:
                        row_cells.append("?")
                    else:
                        row_cells.append("✓" if g.get("correct") else "✗")
                body.append(
                    f"| `{doc_id}` | {info.get('pages', '?')} | "
                    + " | ".join(row_cells) + " |"
                )

        return ReportSection(
            title="Parser × agent-vs-stuffing — long PDFs (sonnet 4.5)",
            headline=True,
            body_md="\n".join(body),
            body_json=m,
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _compute_metrics(
    questions: list[PCQuestion],
    per_arm_results: dict[str, list[ArmResult]],
    per_arm_grades: dict[str, list[GradeResult]],
    active_arms: Iterable[str],
) -> dict[str, Any]:
    """Aggregate per-arm metrics + the user's preprocessing cost overlay."""

    # Sum unique PDF pages — preprocessing pays per unique PDF, not per question.
    pdf_pages: dict[str, int] = {}
    for q in questions:
        pdf_pages.setdefault(q.doc_id, q.pages)

    per_arm: dict[str, dict[str, Any]] = {}
    for arm_name in active_arms:
        results = per_arm_results[arm_name]
        grades = per_arm_grades[arm_name]
        n = len(grades)
        n_correct = sum(1 for g in grades if g.correct)
        f1_sum = sum(g.f1 for g in grades)
        acc_with_ci = accuracy_with_wilson_ci(n_correct, n)

        # LLM cost: sum of per-call cost_micros across questions, then average.
        cost_micros_total = sum(int(r.cost_micros or 0) for r in results)
        llm_cost_per_q = (cost_micros_total / 1_000_000.0) / n if n else 0.0

        # Preprocessing cost depends on which mode this arm corresponds to.
        if arm_name == "native_pdf":
            preprocess_per_page = 0.0
            preprocess_label = "n/a (PDF attached natively)"
        elif arm_name in _LC_ARM_MODE:
            mode = _LC_ARM_MODE[arm_name]
            preprocess_per_page = PREPROCESS_USD_PER_PAGE[mode]
            preprocess_label = f"{mode} tier ($/{mode}/page = ${preprocess_per_page:.4f})"
        elif arm_name == "surfsense_agentic":
            preprocess_per_page = PREPROCESS_USD_PER_PAGE[SURFSENSE_INGEST_MODE]
            preprocess_label = (
                f"{SURFSENSE_INGEST_MODE} tier (ingested by SurfSense at "
                f"processing_mode=premium + vision_llm=on)"
            )
        else:
            preprocess_per_page = 0.0
            preprocess_label = "unknown"

        preprocess_cost_total = sum(
            pages * preprocess_per_page for pages in pdf_pages.values()
        )
        preprocess_cost_per_q = preprocess_cost_total / n if n else 0.0
        total_cost_per_q = llm_cost_per_q + preprocess_cost_per_q

        latencies = sorted(int(r.latency_ms or 0) for r in results)
        latency_median = latencies[len(latencies) // 2] if latencies else 0
        latency_p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else (
            latencies[-1] if latencies else 0
        )

        in_tokens = [int(r.input_tokens or 0) for r in results]
        out_tokens = [int(r.output_tokens or 0) for r in results]

        per_arm[arm_name] = {
            **acc_with_ci.to_dict(),
            "n": n,
            "n_correct": n_correct,
            "f1_mean": f1_sum / n if n else 0.0,
            "llm_cost_per_q": llm_cost_per_q,
            "preprocess_per_page_usd": preprocess_per_page,
            "preprocess_cost_total": preprocess_cost_total,
            "preprocess_cost_per_q": preprocess_cost_per_q,
            "total_cost_per_q": total_cost_per_q,
            "preprocess_label": preprocess_label,
            "latency_ms_median": latency_median,
            "latency_ms_p95": latency_p95,
            "input_tokens_mean": (sum(in_tokens) / len(in_tokens)) if in_tokens else 0.0,
            "output_tokens_mean": (sum(out_tokens) / len(out_tokens)) if out_tokens else 0.0,
        }

    # Per-PDF breakdown (correct / not for each arm)
    per_pdf: dict[str, dict[str, Any]] = {}
    for i, q in enumerate(questions):
        slot = per_pdf.setdefault(q.doc_id, {
            "pages": q.pages,
            "arms": {},
        })
        for arm_name in active_arms:
            slot["arms"].setdefault(arm_name, {
                "correct": per_arm_grades[arm_name][i].correct,
                "f1": per_arm_grades[arm_name][i].f1,
            })

    return {
        "per_arm": per_arm,
        "per_pdf": per_pdf,
        "n_questions": len(questions),
        "n_unique_pdfs": len(pdf_pages),
        "total_pages_in_scope": sum(pdf_pages.values()),
    }


__all__ = ["ParserCompareBenchmark", "PCQuestion"]
