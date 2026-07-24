"""FRAMES runner — Bare LLM (no retrieval) vs SurfSense (multi-hop RAG).

Two arms run paired on every question in the sample:

1. ``BareLlmArm``  — OpenRouter chat completion with the question only.
   Reproduces the published "naive prompting" baseline (40.8% on
   Gemini-Pro-1.5).
2. ``SurfSenseArm`` — POST ``/api/v1/new_chat`` with **no**
   ``mentioned_document_ids`` so the agent retrieves over the entire
   ingested Wikipedia corpus. This is the "multi-step retrieval &
   reasoning" cell in the FRAMES paper.

Open-ended grading: deterministic shortcut + optional LLM-as-judge
(``--no-judge`` to disable). Cost / latency / token aggregates are
collected per arm. Paired stats (McNemar, bootstrap CI) for the
accuracy delta. Per-reasoning-type breakdown to surface where one
arm beats the other (numerical vs temporal vs multi-constraint, ...).
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

from ....core.arms import ArmRequest, ArmResult, BareLlmArm, SurfSenseArm
from ....core.config import utc_iso_timestamp
from ....core.ingest_settings import (
    IngestSettings,
    add_ingest_settings_args,
    format_ingest_settings_md,
    is_settings_header,
)
from ....core.metrics.comparison import (
    bootstrap_delta_ci,
    mcnemar_test,
    paired_aggregate,
)
from ....core.metrics.mc_accuracy import accuracy_with_wilson_ci
from ....core.parse.freeform_answer import extract_freeform_answer
from ....core.providers.openrouter_chat import OpenRouterChatProvider
from ....core.registry import ReportSection, RunArtifact, RunContext
from ....core.scenarios import format_scenario_md
from .grader import GradeResult, JudgeConfig, LlmJudge, grade_many
from .prompt import build_bare_prompt, build_surfsense_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Question shape
# ---------------------------------------------------------------------------


@dataclass
class FramesRunnerQuestion:
    qid: str
    raw_index: int
    question: str
    gold_answer: str
    reasoning_types: list[str]
    document_ids: list[int]  # subset of corpus relevant to this Q (may be empty)
    n_wiki_urls: int
    missing_urls: list[str]


def _load_doc_map(map_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    settings: dict[str, Any] = {}
    with map_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if is_settings_header(row):
                settings = dict(row["__settings__"])
                continue
            rows[str(row["qid"])] = row
    return rows, settings


def _load_questions(
    questions_jsonl: Path,
    doc_map: dict[str, dict[str, Any]],
    *,
    sample_n: int | None,
    reasoning_filter: str | None,
) -> list[FramesRunnerQuestion]:
    out: list[FramesRunnerQuestion] = []
    with questions_jsonl.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            qid = str(row.get("qid") or "").strip()
            if not qid:
                continue
            map_row = doc_map.get(qid, {})
            reasoning = list(row.get("reasoning_types") or [])
            if reasoning_filter and reasoning_filter not in [r.lower() for r in reasoning]:
                continue
            out.append(
                FramesRunnerQuestion(
                    qid=qid,
                    raw_index=int(row.get("raw_index") or 0),
                    question=str(row.get("question") or "").strip(),
                    gold_answer=str(row.get("gold_answer") or "").strip(),
                    reasoning_types=reasoning,
                    document_ids=list(map_row.get("document_ids") or []),
                    n_wiki_urls=int(map_row.get("n_wiki_urls") or 0),
                    missing_urls=list(map_row.get("missing_urls") or []),
                )
            )
    out.sort(key=lambda q: q.raw_index)
    if sample_n is not None and sample_n > 0:
        out = out[:sample_n]
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
    "FRAMES (824 multi-hop Wikipedia questions, 5 reasoning types) — "
    "Bare LLM (no retrieval) vs SurfSense (multi-step RAG over the "
    "Wikipedia corpus). Tests cross-document retrieval + reasoning."
)


_DEFAULT_INGEST_SETTINGS = IngestSettings(
    use_vision_llm=False,
    processing_mode="basic",
)


class FramesBenchmark:
    """Multi-hop Wikipedia RAG vs naive prompting."""

    suite: str = "research"
    name: str = "frames"
    headline: bool = True
    description: str = _DESCRIPTION

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--n",
            dest="sample_n",
            type=int,
            default=None,
            help="Run only the first N questions after filters (default: all 824).",
        )
        parser.add_argument(
            "--reasoning",
            dest="reasoning_filter",
            default=None,
            help=(
                "Filter to questions tagged with this reasoning type "
                "(e.g. 'numerical reasoning', 'temporal reasoning'). "
                "Case-insensitive substring against the upstream tags."
            ),
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=4,
            help="Parallel question workers per arm.",
        )
        parser.add_argument(
            "--scope-mentions",
            dest="scope_mentions",
            action="store_true",
            help=(
                "SurfSense arm: scope retrieval to the per-question "
                "document_ids (oracle-retrieval upper bound). Default "
                "is full-corpus retrieval (the realistic FRAMES setting)."
            ),
        )
        parser.add_argument(
            "--max-output-tokens",
            type=int,
            default=512,
            help="Cap on completion length for both arms.",
        )
        parser.add_argument(
            "--no-judge",
            dest="no_judge",
            action="store_true",
            help=(
                "Disable LLM-as-judge fallback grading; use only the "
                "deterministic grader (faster but more pessimistic)."
            ),
        )
        parser.add_argument(
            "--judge-model",
            dest="judge_model",
            default="anthropic/claude-sonnet-4.5",
            help="OpenRouter slug for the LLM judge (default: claude-sonnet-4.5).",
        )
        parser.add_argument(
            "--judge-concurrency",
            dest="judge_concurrency",
            type=int,
            default=4,
            help="Parallel judge calls (default: 4).",
        )
        # Ingest-only knobs.
        parser.add_argument(
            "--max-questions",
            dest="max_questions",
            type=int,
            default=None,
            help="(ingest only) cap on number of questions to materialise + ingest.",
        )
        parser.add_argument(
            "--upload-batch-size",
            dest="upload_batch_size",
            type=int,
            default=16,
            help="(ingest only) markdown files per fileupload call.",
        )
        parser.add_argument(
            "--skip-upload",
            dest="skip_upload",
            action="store_true",
            help="(ingest only) cache wiki articles locally but don't push to SurfSense.",
        )
        parser.add_argument(
            "--fetch-rps",
            dest="fetch_rate_limit_rps",
            type=float,
            default=2.0,
            help="(ingest only) max requests/second to the Wikipedia API.",
        )
        add_ingest_settings_args(parser, defaults=_DEFAULT_INGEST_SETTINGS)

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import run_ingest

        settings = IngestSettings.merge(_DEFAULT_INGEST_SETTINGS, opts)
        await run_ingest(
            ctx,
            max_questions=opts.get("max_questions"),
            upload_batch_size=int(opts.get("upload_batch_size") or 16),
            skip_upload=bool(opts.get("skip_upload", False)),
            fetch_rate_limit_rps=float(opts.get("fetch_rate_limit_rps") or 2.0),
            settings=settings,
        )

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        sample_n = opts.get("sample_n")
        reasoning_filter = opts.get("reasoning_filter")
        if reasoning_filter:
            reasoning_filter = reasoning_filter.strip().lower() or None
        concurrency = int(opts.get("concurrency") or 4)
        scope_mentions = bool(opts.get("scope_mentions"))
        max_output_tokens = int(opts.get("max_output_tokens") or 512)
        no_judge = bool(opts.get("no_judge"))
        judge_model = str(opts.get("judge_model") or "anthropic/claude-sonnet-4.5")
        judge_concurrency = int(opts.get("judge_concurrency") or 4)

        bench_dir = ctx.benchmark_data_dir()
        questions_jsonl = bench_dir / "questions.jsonl"
        map_path = ctx.maps_dir() / "frames_doc_map.jsonl"
        if not questions_jsonl.exists() or not map_path.exists():
            raise RuntimeError(
                "FRAMES not ingested for this suite. Run "
                "`python -m surfsense_evals ingest research frames` first."
            )

        doc_map, ingest_settings = _load_doc_map(map_path)
        questions = _load_questions(
            questions_jsonl,
            doc_map,
            sample_n=sample_n,
            reasoning_filter=reasoning_filter,
        )
        if not questions:
            raise RuntimeError("No FRAMES questions matched the filters; broaden --reasoning/--n.")
        logger.info("FRAMES: scheduled %d questions", len(questions))

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY env var is required for the bare-LLM arm.")

        bare_provider = OpenRouterChatProvider(
            api_key=api_key,
            base_url=ctx.config.openrouter_base_url,
            model=ctx.native_arm_model,
        )
        bare_arm = BareLlmArm(
            provider=bare_provider,
            max_output_tokens=max_output_tokens,
        )
        surf_arm = SurfSenseArm(
            client=ctx.new_chat_client(),
            search_space_id=ctx.search_space_id,
            ephemeral_threads=True,
        )

        judge: LlmJudge | None = None
        if not no_judge:
            judge = LlmJudge(
                config=JudgeConfig(
                    api_key=api_key,
                    model=judge_model,
                    base_url=ctx.config.openrouter_base_url,
                    concurrency=judge_concurrency,
                )
            )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"

        async def _bare_one(q: FramesRunnerQuestion) -> ArmResult:
            return await bare_arm.answer(_make_bare_request(q, max_output_tokens))

        async def _surf_one(q: FramesRunnerQuestion) -> ArmResult:
            return await surf_arm.answer(_make_surfsense_request(q, scope_mentions=scope_mentions))

        bare_results, surf_results = await asyncio.gather(
            _gather_with_limit((_bare_one(q) for q in questions), concurrency=concurrency),
            _gather_with_limit((_surf_one(q) for q in questions), concurrency=concurrency),
        )

        bare_grades = await _grade_results(questions, bare_results, judge=judge)
        surf_grades = await _grade_results(questions, surf_results, judge=judge)

        with raw_path.open("w", encoding="utf-8") as fh:
            for q, b_res, s_res, b_g, s_g in zip(
                questions, bare_results, surf_results, bare_grades, surf_grades, strict=False
            ):
                meta = {
                    "qid": q.qid,
                    "raw_index": q.raw_index,
                    "reasoning_types": q.reasoning_types,
                    "n_wiki_urls": q.n_wiki_urls,
                    "n_resolved_doc_ids": len(q.document_ids),
                    "n_missing_urls": len(q.missing_urls),
                    "gold": q.gold_answer,
                }
                fh.write(
                    json.dumps(
                        {
                            **meta,
                            **b_res.to_jsonl(),
                            "graded": b_g.to_dict(),
                        }
                    )
                    + "\n"
                )
                fh.write(
                    json.dumps(
                        {
                            **meta,
                            **s_res.to_jsonl(),
                            "graded": s_g.to_dict(),
                        }
                    )
                    + "\n"
                )

        metrics = _compute_metrics(questions, bare_results, surf_results, bare_grades, surf_grades)
        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_questions": len(questions),
                "concurrency": concurrency,
                "reasoning_filter": reasoning_filter,
                "scope_mentions": scope_mentions,
                "no_judge": no_judge,
                "judge_model": judge_model if not no_judge else None,
                "scenario": ctx.scenario,
                "provider_model": ctx.provider_model,
                "native_arm_model": ctx.native_arm_model,
                "vision_provider_model": ctx.vision_provider_model,
                "chat_model_id": ctx.chat_model_id,
                "ingest_settings": ingest_settings,
                "bare_arm_label": "bare_llm",
            },
        )

        manifest_path = run_dir / "run_artifact.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "suite": self.suite,
                    "benchmark": self.name,
                    "raw_path": "raw.jsonl",
                    "metrics": metrics,
                    "extra": artifact.extra,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return artifact

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="FRAMES — Bare LLM vs SurfSense (multi-hop Wikipedia RAG)",
                headline=True,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        bare = m.get("bare", {})
        surf = m.get("surfsense", {})
        delta = m.get("delta", {})
        per_reasoning = m.get("per_reasoning", {})
        extra = latest.extra

        body_lines: list[str] = []
        body_lines.append(
            f"- Sample size: {extra.get('n_questions', '?')} questions "
            f"(reasoning filter: `{extra.get('reasoning_filter') or 'none'}`, "
            f"scope-mentions: `{extra.get('scope_mentions', False)}`, "
            f"judge: `{extra.get('judge_model') or 'deterministic-only'}`)."
        )
        body_lines.append(format_scenario_md(extra))
        body_lines.append(format_ingest_settings_md(extra.get("ingest_settings")))
        body_lines.append(
            "- Bare LLM arm (OpenRouter chat, no retrieval, "
            f"`{extra.get('native_arm_model') or extra.get('provider_model', '?')}`):"
        )
        body_lines.append(_arm_summary_lines(bare, indent="  "))
        body_lines.append(
            "- SurfSense arm (`POST /api/v1/new_chat`, multi-step RAG, "
            f"`{extra.get('provider_model', '?')}`):"
        )
        body_lines.append(_arm_summary_lines(surf, indent="  "))
        body_lines.append("- Delta (paired):")
        body_lines.append(
            f"  - Accuracy: SurfSense {_pp(delta.get('accuracy_pp'))} pp "
            f"(McNemar p={_fmt(delta.get('mcnemar_p_value'), 4)}, "
            f"method={delta.get('mcnemar_method')})"
        )
        body_lines.append(
            f"  - Bootstrap 95% CI on accuracy delta: "
            f"[{_pp(delta.get('bootstrap_ci_low'))}pp, {_pp(delta.get('bootstrap_ci_high'))}pp]"
        )
        body_lines.append(
            f"  - Cost / question: bare ${_dollars(bare.get('cost_micros_mean'))}, "
            f"surfsense ${_dollars(surf.get('cost_micros_mean'))} "
            f"(SurfSense delta {_pct_change(delta.get('cost_micros_pct'))})"
        )
        body_lines.append(
            f"  - Latency p50: bare {_ms_to_s(bare.get('latency_ms_median'))}, "
            f"surfsense {_ms_to_s(surf.get('latency_ms_median'))} "
            f"(SurfSense delta {_pct_change(delta.get('latency_ms_pct'))})"
        )
        if per_reasoning:
            body_lines.append("- Per-reasoning-type split (accuracy delta in pp):")
            for tag, vals in sorted(per_reasoning.items()):
                body_lines.append(
                    f"  - {tag}: SurfSense {_pp(vals.get('delta_accuracy_pp'))} pp "
                    f"(n={vals.get('n')}, bare acc={vals.get('bare_accuracy', 0) * 100:.1f}%, "
                    f"surf acc={vals.get('surfsense_accuracy', 0) * 100:.1f}%)"
                )

        return ReportSection(
            title="FRAMES — Bare LLM vs SurfSense (multi-hop Wikipedia RAG)",
            headline=True,
            body_md="\n".join(body_lines),
            body_json=m,
        )


# ---------------------------------------------------------------------------
# Per-question helpers
# ---------------------------------------------------------------------------


def _make_bare_request(q: FramesRunnerQuestion, max_tokens: int) -> ArmRequest:
    return ArmRequest(
        question_id=q.qid,
        prompt=build_bare_prompt(q.question),
        options={"max_tokens": max_tokens},
    )


def _make_surfsense_request(q: FramesRunnerQuestion, *, scope_mentions: bool) -> ArmRequest:
    mentions: list[int] | None = None
    if scope_mentions and q.document_ids:
        mentions = list(q.document_ids)
    return ArmRequest(
        question_id=q.qid,
        prompt=build_surfsense_prompt(q.question),
        mentioned_document_ids=mentions,
    )


async def _grade_results(
    questions: list[FramesRunnerQuestion],
    results: list[ArmResult],
    *,
    judge: LlmJudge | None,
) -> list[GradeResult]:
    rows: list[tuple[str, str, str, str]] = []
    for q, r in zip(questions, results, strict=False):
        pred = extract_freeform_answer(r.raw_text or "")
        rows.append((q.qid, q.question, q.gold_answer, pred))
    return await grade_many(rows=rows, judge=judge)


# ---------------------------------------------------------------------------
# Metrics aggregation
# ---------------------------------------------------------------------------


def _compute_metrics(
    questions: list[FramesRunnerQuestion],
    bare_results: list[ArmResult],
    surf_results: list[ArmResult],
    bare_grades: list[GradeResult],
    surf_grades: list[GradeResult],
) -> dict[str, Any]:
    bare_correct = [g.correct for g in bare_grades]
    surf_correct = [g.correct for g in surf_grades]

    bare_costs = [float(r.cost_micros) for r in bare_results]
    surf_costs = [float(r.cost_micros) for r in surf_results]
    bare_latencies = [float(r.latency_ms) for r in bare_results]
    surf_latencies = [float(r.latency_ms) for r in surf_results]
    bare_in_tokens = [float(r.input_tokens) for r in bare_results]
    bare_out_tokens = [float(r.output_tokens) for r in bare_results]

    bare_acc = accuracy_with_wilson_ci(sum(bare_correct), len(bare_correct))
    surf_acc = accuracy_with_wilson_ci(sum(surf_correct), len(surf_correct))
    mc = mcnemar_test(bare_correct, surf_correct)
    boot = bootstrap_delta_ci(bare_correct, surf_correct, n_resamples=2000)

    bare_cost_agg = paired_aggregate(bare_costs)
    surf_cost_agg = paired_aggregate(surf_costs)
    bare_latency_agg = paired_aggregate(bare_latencies)
    surf_latency_agg = paired_aggregate(surf_latencies)
    cost_pct = _safe_pct(surf_cost_agg.mean, bare_cost_agg.mean)
    latency_pct = _safe_pct(surf_latency_agg.median, bare_latency_agg.median)

    # Per-reasoning-type breakdown. Each question may carry multiple
    # reasoning tags; we count it under each tag (so totals don't
    # equal len(questions) — the reader is expected to look at the
    # per-tag ``n``).
    per_reasoning_pairs: dict[str, list[tuple[bool, bool]]] = {}
    for q, b_ok, s_ok in zip(questions, bare_correct, surf_correct, strict=False):
        tags = q.reasoning_types or ["(untagged)"]
        for tag in tags:
            per_reasoning_pairs.setdefault(tag, []).append((b_ok, s_ok))

    per_reasoning: dict[str, dict[str, Any]] = {}
    for tag, pairs in per_reasoning_pairs.items():
        b_correct = [a for a, _ in pairs]
        s_correct = [b for _, b in pairs]
        per_reasoning[tag] = {
            "n": len(pairs),
            "bare_accuracy": (sum(b_correct) / len(pairs)) if pairs else 0.0,
            "surfsense_accuracy": (sum(s_correct) / len(pairs)) if pairs else 0.0,
            "delta_accuracy_pp": (
                100.0 * (sum(s_correct) - sum(b_correct)) / len(pairs) if pairs else 0.0
            ),
        }

    grader_methods = {
        "bare": _count_methods(bare_grades),
        "surfsense": _count_methods(surf_grades),
    }

    return {
        "bare": {
            **bare_acc.to_dict(),
            "cost_micros_mean": bare_cost_agg.mean,
            "cost_micros_median": bare_cost_agg.median,
            "latency_ms_mean": bare_latency_agg.mean,
            "latency_ms_median": bare_latency_agg.median,
            "latency_ms_p95": bare_latency_agg.p95,
            "input_tokens_mean": (sum(bare_in_tokens) / len(bare_in_tokens))
            if bare_in_tokens
            else 0.0,
            "output_tokens_mean": (sum(bare_out_tokens) / len(bare_out_tokens))
            if bare_out_tokens
            else 0.0,
        },
        "surfsense": {
            **surf_acc.to_dict(),
            "cost_micros_mean": surf_cost_agg.mean,
            "cost_micros_median": surf_cost_agg.median,
            "latency_ms_mean": surf_latency_agg.mean,
            "latency_ms_median": surf_latency_agg.median,
            "latency_ms_p95": surf_latency_agg.p95,
        },
        "delta": {
            "accuracy_pp": 100.0 * (surf_acc.accuracy - bare_acc.accuracy),
            "mcnemar_p_value": mc.p_value,
            "mcnemar_method": mc.method,
            "mcnemar_b_bare_only": mc.b,
            "mcnemar_c_surfsense_only": mc.c,
            "bootstrap_ci_low": 100.0 * boot.ci_low,
            "bootstrap_ci_high": 100.0 * boot.ci_high,
            "cost_micros_pct": cost_pct,
            "latency_ms_pct": latency_pct,
        },
        "per_reasoning": per_reasoning,
        "grader_methods": grader_methods,
    }


def _count_methods(grades: list[GradeResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for g in grades:
        out[g.method] = out.get(g.method, 0) + 1
    return out


def _safe_pct(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return 100.0 * (numerator - denominator) / denominator


# ---------------------------------------------------------------------------
# Tiny formatting helpers used by report_section
# ---------------------------------------------------------------------------


def _arm_summary_lines(d: dict[str, Any], *, indent: str) -> str:
    if not d:
        return f"{indent}(no data)"
    acc = d.get("accuracy", 0.0)
    low = d.get("ci_low", 0.0)
    high = d.get("ci_high", 0.0)
    lines = [
        f"{indent}- Accuracy: {acc * 100:.1f}% (Wilson 95% CI: {low * 100:.1f}% – {high * 100:.1f}%)",
        f"{indent}- Cost / question: ${_dollars(d.get('cost_micros_mean'))} (mean), "
        f"${_dollars(d.get('cost_micros_median'))} (median)",
        f"{indent}- Latency: p50 {_ms_to_s(d.get('latency_ms_median'))}, "
        f"p95 {_ms_to_s(d.get('latency_ms_p95'))}",
    ]
    if "input_tokens_mean" in d:
        lines.append(
            f"{indent}- Mean tokens / question: in {d.get('input_tokens_mean', 0):.0f}, "
            f"out {d.get('output_tokens_mean', 0):.0f}"
        )
    return "\n".join(lines)


def _dollars(micros: Any) -> str:
    if micros is None:
        return "?"
    try:
        return f"{(float(micros) / 1_000_000):.4f}"
    except (TypeError, ValueError):
        return "?"


def _ms_to_s(ms: Any) -> str:
    if ms is None:
        return "?"
    try:
        return f"{float(ms) / 1000:.1f}s"
    except (TypeError, ValueError):
        return "?"


def _pp(value: Any) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):+.1f}"
    except (TypeError, ValueError):
        return "?"


def _pct_change(value: Any) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):+.0f}%"
    except (TypeError, ValueError):
        return "?"


def _fmt(value: Any, ndigits: int) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return "?"


__all__ = ["FramesBenchmark", "FramesRunnerQuestion"]
