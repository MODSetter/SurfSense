"""CRAG runner — Bare LLM vs Long-Context LLM vs SurfSense.

Three arms run paired on every question in the sample. All three
answer with the same model (CRAG is a head-to-head benchmark, not a
cost-arbitrage benchmark). The arms differ only in *what they see*:

1. ``bare_llm``      — chat completion with the question only
   (paper baseline ≤34%).
2. ``long_context``  — same model, but the user message also includes
   the extracted text of all 5 web pages (paper baseline ~44%).
3. ``surfsense``     — POST ``/api/v1/new_chat`` with retrieval scoped
   to the question's 5 ingested pages via ``mentioned_document_ids``.
   The agent retrieves and reasons; we only grade the final answer.

Grading: 3-class CRAG rubric — correct/missing/incorrect — with
deterministic shortcuts and an LLM-as-judge fallback. Headline is
the **truthfulness score** ``(#correct - #incorrect) / total``, the
metric the CRAG paper and KDD Cup 2024 leaderboard use.

We keep paired stats (McNemar + bootstrap CI) on the **correct**
flag for each arm pair (long_context vs bare, surfsense vs
long_context, surfsense vs bare) so the report can call out exactly
where the lift comes from. Per-domain and per-question-type breakdowns
surface where SurfSense beats long-context (e.g. multi-hop / set
questions where retrieval-then-reason wins over stuff-it-all-in).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
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
from .grader import (
    CragGradeResult,
    CragGradeRow,
    CragJudgeConfig,
    CragLlmJudge,
    grade_many,
)
from .ingest import read_page_markdown
from .prompt import (
    build_bare_prompt,
    build_long_context_prompt,
    build_surfsense_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Question shape (post-ingest)
# ---------------------------------------------------------------------------


@dataclass
class CragRunnerQuestion:
    qid: str
    raw_index: int
    question: str
    gold_answer: str
    alt_answers: list[str]
    domain: str
    question_type: str
    static_or_dynamic: str
    popularity: str
    query_time: str
    page_filenames: list[str]
    document_ids: list[int]
    missing_pages: list[str] = field(default_factory=list)


def _load_doc_map(map_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
            rows.append(row)
    return rows, settings


def _filter_questions(
    rows: list[dict[str, Any]],
    *,
    sample_n: int | None,
    domain_filter: str | None,
    qtype_filter: str | None,
) -> list[CragRunnerQuestion]:
    out: list[CragRunnerQuestion] = []
    for row in rows:
        domain = str(row.get("domain") or "").lower()
        qtype = str(row.get("question_type") or "").lower()
        if domain_filter and domain_filter != domain:
            continue
        if qtype_filter and qtype_filter not in qtype:
            continue
        out.append(
            CragRunnerQuestion(
                qid=str(row.get("qid") or "").strip(),
                raw_index=int(row.get("raw_index") or 0),
                question=str(row.get("question") or "").strip(),
                gold_answer=str(row.get("gold_answer") or "").strip(),
                alt_answers=list(row.get("alt_answers") or []),
                domain=domain,
                question_type=qtype,
                static_or_dynamic=str(row.get("static_or_dynamic") or "").lower(),
                popularity=str(row.get("popularity") or "").lower(),
                query_time=str(row.get("query_time") or "").strip(),
                page_filenames=list(row.get("page_filenames") or []),
                document_ids=list(row.get("document_ids") or []),
                missing_pages=list(row.get("missing_pages") or []),
            )
        )
    out.sort(key=lambda q: q.raw_index)
    if sample_n is not None and sample_n > 0:
        out = out[:sample_n]
    return out


# ---------------------------------------------------------------------------
# Concurrency helper
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
    "CRAG (Comprehensive RAG Benchmark, Meta KDD Cup 2024) — three "
    "arms (Bare LLM / Long-Context LLM / SurfSense) over the same "
    "5-page-per-question CRAG corpus. Tests competitive RAG vs naive "
    "context-stuffing; CRAG truthfulness score is the headline metric."
)


_DEFAULT_INGEST_SETTINGS = IngestSettings(
    use_vision_llm=False,
    processing_mode="basic",
)


class CragBenchmark:
    """3-arm CRAG runner: bare vs long-context vs SurfSense."""

    suite: str = "research"
    name: str = "crag"
    headline: bool = True
    description: str = _DESCRIPTION

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--n",
            dest="sample_n",
            type=int,
            default=None,
            help="Run only the first N questions after filters.",
        )
        parser.add_argument(
            "--domain",
            dest="domain_filter",
            default=None,
            help="Filter to a single CRAG domain (finance|music|movie|sports|open).",
        )
        parser.add_argument(
            "--qtype",
            dest="qtype_filter",
            default=None,
            help=(
                "Filter to questions whose question_type contains this "
                "substring (case-insensitive). Examples: 'multi-hop', "
                "'comparison', 'false_premise'."
            ),
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=4,
            help="Parallel question workers per arm.",
        )
        parser.add_argument(
            "--max-output-tokens",
            type=int,
            default=512,
            help="Cap on completion length for the chat-completion arms.",
        )
        parser.add_argument(
            "--per-page-char-cap",
            dest="per_page_char_cap",
            type=int,
            default=12_000,
            help="Long-context arm: max chars per page before truncation (default 12k).",
        )
        parser.add_argument(
            "--skip-bare",
            dest="skip_bare",
            action="store_true",
            help="Skip the bare-LLM arm (saves cost on re-runs).",
        )
        parser.add_argument(
            "--skip-long-context",
            dest="skip_long_context",
            action="store_true",
            help="Skip the long-context arm.",
        )
        parser.add_argument(
            "--skip-surfsense",
            dest="skip_surfsense",
            action="store_true",
            help="Skip the SurfSense arm (useful when iterating on the LLM arms only).",
        )
        parser.add_argument(
            "--no-mention-scope",
            dest="no_mention_scope",
            action="store_true",
            help=(
                "SurfSense arm: don't pass mentioned_document_ids; let "
                "the agent retrieve over the entire SearchSpace. Default "
                "is to scope to the question's 5 ingested pages "
                "(matches CRAG protocol)."
            ),
        )
        parser.add_argument(
            "--no-judge",
            dest="no_judge",
            action="store_true",
            help="Disable the LLM-as-judge fallback grader.",
        )
        parser.add_argument(
            "--judge-model",
            dest="judge_model",
            default="anthropic/claude-sonnet-4.5",
            help="OpenRouter slug for the LLM judge.",
        )
        parser.add_argument(
            "--judge-concurrency",
            dest="judge_concurrency",
            type=int,
            default=4,
            help="Parallel judge calls.",
        )
        # Ingest knobs
        parser.add_argument(
            "--n-questions",
            dest="n_questions",
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
            help="(ingest only) extract pages locally but don't push to SurfSense.",
        )
        parser.add_argument(
            "--overwrite-extract",
            dest="overwrite_extract",
            action="store_true",
            help="(ingest only) re-run trafilatura even when cached markdown exists.",
        )
        parser.add_argument(
            "--sample-seed",
            dest="sample_seed",
            type=int,
            default=17,
            help="(ingest only) RNG seed for the stratified sample.",
        )
        add_ingest_settings_args(parser, defaults=_DEFAULT_INGEST_SETTINGS)

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import run_ingest

        settings = IngestSettings.merge(_DEFAULT_INGEST_SETTINGS, opts)
        await run_ingest(
            ctx,
            n_questions=opts.get("n_questions"),
            upload_batch_size=int(opts.get("upload_batch_size") or 16),
            skip_upload=bool(opts.get("skip_upload", False)),
            overwrite_extract=bool(opts.get("overwrite_extract", False)),
            settings=settings,
            sample_seed=int(opts.get("sample_seed") or 17),
        )

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        sample_n = opts.get("sample_n")
        domain_filter = (opts.get("domain_filter") or "").strip().lower() or None
        qtype_filter = (opts.get("qtype_filter") or "").strip().lower() or None
        concurrency = int(opts.get("concurrency") or 4)
        max_output_tokens = int(opts.get("max_output_tokens") or 512)
        per_page_char_cap = int(opts.get("per_page_char_cap") or 12_000)
        skip_bare = bool(opts.get("skip_bare"))
        skip_long_context = bool(opts.get("skip_long_context"))
        skip_surfsense = bool(opts.get("skip_surfsense"))
        no_mention_scope = bool(opts.get("no_mention_scope"))
        no_judge = bool(opts.get("no_judge"))
        judge_model = str(opts.get("judge_model") or "anthropic/claude-sonnet-4.5")
        judge_concurrency = int(opts.get("judge_concurrency") or 4)

        bench_dir = ctx.benchmark_data_dir()
        map_path = ctx.maps_dir() / "crag_doc_map.jsonl"
        if not map_path.exists():
            raise RuntimeError(
                "CRAG not ingested for this suite. Run "
                "`python -m surfsense_evals ingest research crag --n-questions 200` first."
            )

        rows, ingest_settings = _load_doc_map(map_path)
        questions = _filter_questions(
            rows,
            sample_n=sample_n,
            domain_filter=domain_filter,
            qtype_filter=qtype_filter,
        )
        if not questions:
            raise RuntimeError(
                "No CRAG questions matched the filters; broaden --n / --domain / --qtype."
            )
        logger.info("CRAG: scheduled %d questions", len(questions))

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key and not (skip_bare and skip_long_context):
            raise RuntimeError(
                "OPENROUTER_API_KEY env var is required for the bare / long-context arms."
            )

        bare_arm = long_context_arm = surf_arm = None
        chat_provider: OpenRouterChatProvider | None = None
        if not (skip_bare and skip_long_context):
            chat_provider = OpenRouterChatProvider(
                api_key=api_key or "",
                base_url=ctx.config.openrouter_base_url,
                model=ctx.native_arm_model,
            )
        if not skip_bare and chat_provider is not None:
            bare_arm = BareLlmArm(
                provider=chat_provider,
                max_output_tokens=max_output_tokens,
                name="bare_llm",
            )
        if not skip_long_context and chat_provider is not None:
            long_context_arm = BareLlmArm(
                provider=chat_provider,
                max_output_tokens=max_output_tokens,
                name="long_context",
            )
        if not skip_surfsense:
            surf_arm = SurfSenseArm(
                client=ctx.new_chat_client(),
                search_space_id=ctx.search_space_id,
                ephemeral_threads=True,
            )

        judge: CragLlmJudge | None = None
        if not no_judge:
            if not api_key:
                logger.warning("CRAG: --no-judge implied (no OPENROUTER_API_KEY for judge)")
            else:
                judge = CragLlmJudge(
                    config=CragJudgeConfig(
                        api_key=api_key,
                        model=judge_model,
                        base_url=ctx.config.openrouter_base_url,
                        concurrency=judge_concurrency,
                    )
                )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"

        async def _bare_one(q: CragRunnerQuestion) -> ArmResult:
            assert bare_arm is not None
            return await bare_arm.answer(_make_bare_request(q, max_output_tokens))

        async def _long_context_one(q: CragRunnerQuestion) -> ArmResult:
            assert long_context_arm is not None
            return await long_context_arm.answer(
                _make_long_context_request(q, bench_dir, max_output_tokens, per_page_char_cap)
            )

        async def _surf_one(q: CragRunnerQuestion) -> ArmResult:
            assert surf_arm is not None
            return await surf_arm.answer(
                _make_surfsense_request(q, scope_to_pages=not no_mention_scope)
            )

        # Run all enabled arms concurrently. Each arm is itself
        # internally concurrency-bounded.
        tasks: list[Any] = []
        if bare_arm is not None:
            tasks.append(
                _gather_with_limit((_bare_one(q) for q in questions), concurrency=concurrency)
            )
        else:
            tasks.append(_make_skipped_results(questions, "bare_llm"))
        if long_context_arm is not None:
            tasks.append(
                _gather_with_limit(
                    (_long_context_one(q) for q in questions), concurrency=concurrency
                )
            )
        else:
            tasks.append(_make_skipped_results(questions, "long_context"))
        if surf_arm is not None:
            tasks.append(
                _gather_with_limit((_surf_one(q) for q in questions), concurrency=concurrency)
            )
        else:
            tasks.append(_make_skipped_results(questions, "surfsense"))

        bare_results, long_context_results, surf_results = await asyncio.gather(*tasks)

        bare_grades = (
            await _grade_results(questions, bare_results, judge=judge)
            if bare_arm
            else _empty_grades(questions)
        )
        lc_grades = (
            await _grade_results(questions, long_context_results, judge=judge)
            if long_context_arm
            else _empty_grades(questions)
        )
        surf_grades = (
            await _grade_results(questions, surf_results, judge=judge)
            if surf_arm
            else _empty_grades(questions)
        )

        with raw_path.open("w", encoding="utf-8") as fh:
            for q, b_res, l_res, s_res, b_g, l_g, s_g in zip(
                questions,
                bare_results,
                long_context_results,
                surf_results,
                bare_grades,
                lc_grades,
                surf_grades,
                strict=False,
            ):
                meta = {
                    "qid": q.qid,
                    "raw_index": q.raw_index,
                    "domain": q.domain,
                    "question_type": q.question_type,
                    "static_or_dynamic": q.static_or_dynamic,
                    "popularity": q.popularity,
                    "n_pages": len(q.page_filenames),
                    "n_doc_ids": len(q.document_ids),
                    "gold": q.gold_answer,
                    "alt_answers": q.alt_answers,
                }
                for res, grade in (
                    (b_res, b_g),
                    (l_res, l_g),
                    (s_res, s_g),
                ):
                    fh.write(
                        json.dumps(
                            {
                                **meta,
                                **res.to_jsonl(),
                                "graded": grade.to_dict(),
                            }
                        )
                        + "\n"
                    )

        metrics = _compute_metrics(
            questions=questions,
            bare_results=bare_results,
            long_context_results=long_context_results,
            surf_results=surf_results,
            bare_grades=bare_grades,
            lc_grades=lc_grades,
            surf_grades=surf_grades,
            arms_active={
                "bare_llm": bare_arm is not None,
                "long_context": long_context_arm is not None,
                "surfsense": surf_arm is not None,
            },
        )
        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_questions": len(questions),
                "concurrency": concurrency,
                "domain_filter": domain_filter,
                "qtype_filter": qtype_filter,
                "no_mention_scope": no_mention_scope,
                "no_judge": no_judge,
                "judge_model": judge_model if not no_judge else None,
                "scenario": ctx.scenario,
                "provider_model": ctx.provider_model,
                "native_arm_model": ctx.native_arm_model,
                "vision_provider_model": ctx.vision_provider_model,
                "chat_model_id": ctx.chat_model_id,
                "ingest_settings": ingest_settings,
                "per_page_char_cap": per_page_char_cap,
                "max_output_tokens": max_output_tokens,
                "arms_active": {
                    "bare_llm": bare_arm is not None,
                    "long_context": long_context_arm is not None,
                    "surfsense": surf_arm is not None,
                },
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
                title="CRAG — Bare LLM vs Long-Context LLM vs SurfSense",
                headline=True,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        bare = m.get("bare_llm", {})
        lc = m.get("long_context", {})
        surf = m.get("surfsense", {})
        deltas = m.get("deltas", {})
        per_domain = m.get("per_domain", {})
        per_qtype = m.get("per_question_type", {})
        extra = latest.extra

        body_lines: list[str] = []
        body_lines.append(
            f"- Sample size: {extra.get('n_questions', '?')} questions "
            f"(domain filter: `{extra.get('domain_filter') or 'none'}`, "
            f"qtype filter: `{extra.get('qtype_filter') or 'none'}`, "
            f"judge: `{extra.get('judge_model') or 'deterministic-only'}`)."
        )
        body_lines.append(format_scenario_md(extra))
        body_lines.append(format_ingest_settings_md(extra.get("ingest_settings")))
        active = extra.get("arms_active") or {}
        if not active.get("bare_llm", True):
            body_lines.append("- Bare-LLM arm: SKIPPED.")
        else:
            body_lines.append(
                f"- Bare-LLM arm (`{extra.get('native_arm_model') or '?'}`, no retrieval):"
            )
            body_lines.append(_arm_summary_lines(bare, indent="  "))
        if not active.get("long_context", True):
            body_lines.append("- Long-context arm: SKIPPED.")
        else:
            body_lines.append(
                f"- Long-context arm (`{extra.get('native_arm_model') or '?'}`, "
                f"all 5 pages stuffed into prompt; per-page cap "
                f"{extra.get('per_page_char_cap', 12_000):,} chars):"
            )
            body_lines.append(_arm_summary_lines(lc, indent="  "))
        if not active.get("surfsense", True):
            body_lines.append("- SurfSense arm: SKIPPED.")
        else:
            body_lines.append(
                f"- SurfSense arm (`{extra.get('provider_model', '?')}`, retrieval over "
                f"{'whole SearchSpace' if extra.get('no_mention_scope') else 'per-question 5 pages'}):"
            )
            body_lines.append(_arm_summary_lines(surf, indent="  "))

        body_lines.append("- Headline truthfulness scores (CRAG paper rubric):")
        for label, key in (
            ("Bare LLM", "bare_llm"),
            ("Long-Context", "long_context"),
            ("SurfSense", "surfsense"),
        ):
            d = m.get(key, {})
            body_lines.append(
                f"  - {label}: score={_signed_pct(d.get('truthfulness_score'))}, "
                f"correct={_pct(d.get('correct_rate'))}, "
                f"missing={_pct(d.get('missing_rate'))}, "
                f"incorrect={_pct(d.get('incorrect_rate'))}"
            )

        if deltas:
            body_lines.append("- Pairwise deltas (paired):")
            for label, key in (
                ("SurfSense vs Bare", "surfsense_vs_bare"),
                ("SurfSense vs Long-Context", "surfsense_vs_long_context"),
                ("Long-Context vs Bare", "long_context_vs_bare"),
            ):
                d = deltas.get(key)
                if not d:
                    continue
                body_lines.append(
                    f"  - {label}: accuracy {_pp(d.get('accuracy_pp'))} pp, "
                    f"truthfulness {_pp(d.get('truthfulness_score_pp'))} pp "
                    f"(McNemar p={_fmt(d.get('mcnemar_p_value'), 4)}, "
                    f"method={d.get('mcnemar_method')}; bootstrap CI on accuracy "
                    f"[{_pp(d.get('bootstrap_ci_low'))}pp, {_pp(d.get('bootstrap_ci_high'))}pp])"
                )

        if per_domain:
            body_lines.append("- Per-domain truthfulness score (active arms):")
            for domain in sorted(per_domain.keys()):
                row = per_domain[domain]
                pieces: list[str] = [f"  - {domain} (n={row.get('n')}):"]
                for arm in ("bare_llm", "long_context", "surfsense"):
                    if arm not in row:
                        continue
                    pieces.append(f"{arm}={_signed_pct(row[arm].get('truthfulness_score'))}")
                body_lines.append(" ".join(pieces))

        if per_qtype:
            body_lines.append("- Per-question-type truthfulness score (active arms):")
            for qtype in sorted(per_qtype.keys()):
                row = per_qtype[qtype]
                pieces = [f"  - {qtype} (n={row.get('n')}):"]
                for arm in ("bare_llm", "long_context", "surfsense"):
                    if arm not in row:
                        continue
                    pieces.append(f"{arm}={_signed_pct(row[arm].get('truthfulness_score'))}")
                body_lines.append(" ".join(pieces))

        return ReportSection(
            title="CRAG — Bare LLM vs Long-Context LLM vs SurfSense",
            headline=True,
            body_md="\n".join(body_lines),
            body_json=m,
        )


# ---------------------------------------------------------------------------
# Per-question helpers
# ---------------------------------------------------------------------------


def _make_bare_request(q: CragRunnerQuestion, max_tokens: int) -> ArmRequest:
    return ArmRequest(
        question_id=q.qid,
        prompt=build_bare_prompt(q.question, query_time=q.query_time),
        options={"max_tokens": max_tokens},
    )


def _make_long_context_request(
    q: CragRunnerQuestion,
    bench_dir: Path,
    max_tokens: int,
    per_page_char_cap: int,
) -> ArmRequest:
    contexts: list[tuple[str, str]] = []
    for fn in q.page_filenames:
        text = read_page_markdown(bench_dir, fn) or ""
        if not text.strip():
            continue
        # Use the filename stem as a stable title fallback (URLs are
        # already in the markdown body's "Source:" header line).
        contexts.append((Path(fn).stem, text))
    prompt = build_long_context_prompt(
        q.question,
        contexts=contexts,
        query_time=q.query_time,
        per_page_char_cap=per_page_char_cap,
    )
    return ArmRequest(
        question_id=q.qid,
        prompt=prompt,
        options={"max_tokens": max_tokens},
    )


def _make_surfsense_request(q: CragRunnerQuestion, *, scope_to_pages: bool) -> ArmRequest:
    mentions: list[int] | None = None
    if scope_to_pages and q.document_ids:
        mentions = list(q.document_ids)
    return ArmRequest(
        question_id=q.qid,
        prompt=build_surfsense_prompt(q.question, query_time=q.query_time),
        mentioned_document_ids=mentions,
    )


async def _grade_results(
    questions: list[CragRunnerQuestion],
    results: list[ArmResult],
    *,
    judge: CragLlmJudge | None,
) -> list[CragGradeResult]:
    rows: list[CragGradeRow] = []
    for q, r in zip(questions, results, strict=False):
        pred = extract_freeform_answer(r.raw_text or "")
        rows.append(
            CragGradeRow(
                qid=q.qid,
                question=q.question,
                gold=q.gold_answer,
                alt_answers=q.alt_answers,
                pred=pred,
                question_type=q.question_type,
            )
        )
    return await grade_many(rows=rows, judge=judge)


def _empty_grades(questions: list[CragRunnerQuestion]) -> list[CragGradeResult]:
    return [CragGradeResult(grade="missing", score=0, method="skipped_arm") for _ in questions]


async def _make_skipped_results(
    questions: list[CragRunnerQuestion],
    arm_name: str,
) -> list[ArmResult]:
    """Stand-in results so downstream code can assume parallel lists."""

    return [
        ArmResult(arm=arm_name, question_id=q.qid, raw_text="", error="skipped") for q in questions
    ]


# ---------------------------------------------------------------------------
# Metrics aggregation
# ---------------------------------------------------------------------------


def _arm_truthfulness(grades: list[CragGradeResult]) -> dict[str, Any]:
    """Per-arm headline numbers — accuracy + 3-class rates + truthfulness."""

    n = len(grades) or 1
    n_correct = sum(g.correct for g in grades)
    n_missing = sum(g.missing for g in grades)
    n_incorrect = sum(g.incorrect for g in grades)
    return {
        "n_total": len(grades),
        "n_correct": n_correct,
        "n_missing": n_missing,
        "n_incorrect": n_incorrect,
        "correct_rate": n_correct / n,
        "missing_rate": n_missing / n,
        "incorrect_rate": n_incorrect / n,
        "truthfulness_score": (n_correct - n_incorrect) / n,
    }


def _compute_metrics(
    *,
    questions: list[CragRunnerQuestion],
    bare_results: list[ArmResult],
    long_context_results: list[ArmResult],
    surf_results: list[ArmResult],
    bare_grades: list[CragGradeResult],
    lc_grades: list[CragGradeResult],
    surf_grades: list[CragGradeResult],
    arms_active: dict[str, bool],
) -> dict[str, Any]:
    bare_correct = [g.correct for g in bare_grades]
    lc_correct = [g.correct for g in lc_grades]
    surf_correct = [g.correct for g in surf_grades]

    bare_acc = accuracy_with_wilson_ci(sum(bare_correct), len(bare_correct))
    lc_acc = accuracy_with_wilson_ci(sum(lc_correct), len(lc_correct))
    surf_acc = accuracy_with_wilson_ci(sum(surf_correct), len(surf_correct))

    bare_t = _arm_truthfulness(bare_grades)
    lc_t = _arm_truthfulness(lc_grades)
    surf_t = _arm_truthfulness(surf_grades)

    def _arm_block(
        results: list[ArmResult],
        acc: Any,
        truthfulness: dict[str, Any],
    ) -> dict[str, Any]:
        costs = [float(r.cost_micros) for r in results]
        latencies = [float(r.latency_ms) for r in results]
        ins = [float(r.input_tokens) for r in results]
        outs = [float(r.output_tokens) for r in results]
        cost_agg = paired_aggregate(costs)
        lat_agg = paired_aggregate(latencies)
        return {
            **acc.to_dict(),
            **truthfulness,
            "cost_micros_mean": cost_agg.mean,
            "cost_micros_median": cost_agg.median,
            "latency_ms_mean": lat_agg.mean,
            "latency_ms_median": lat_agg.median,
            "latency_ms_p95": lat_agg.p95,
            "input_tokens_mean": (sum(ins) / len(ins)) if ins else 0.0,
            "output_tokens_mean": (sum(outs) / len(outs)) if outs else 0.0,
        }

    out: dict[str, Any] = {
        "bare_llm": _arm_block(bare_results, bare_acc, bare_t),
        "long_context": _arm_block(long_context_results, lc_acc, lc_t),
        "surfsense": _arm_block(surf_results, surf_acc, surf_t),
    }

    deltas: dict[str, Any] = {}
    for label, ref_correct, ref_t, chal_correct, chal_t, both_active in (
        (
            "surfsense_vs_bare",
            bare_correct,
            bare_t,
            surf_correct,
            surf_t,
            arms_active.get("bare_llm") and arms_active.get("surfsense"),
        ),
        (
            "surfsense_vs_long_context",
            lc_correct,
            lc_t,
            surf_correct,
            surf_t,
            arms_active.get("long_context") and arms_active.get("surfsense"),
        ),
        (
            "long_context_vs_bare",
            bare_correct,
            bare_t,
            lc_correct,
            lc_t,
            arms_active.get("bare_llm") and arms_active.get("long_context"),
        ),
    ):
        if not both_active:
            continue
        mc = mcnemar_test(ref_correct, chal_correct)
        boot = bootstrap_delta_ci(ref_correct, chal_correct, n_resamples=2000)
        deltas[label] = {
            "accuracy_pp": 100.0
            * (sum(chal_correct) - sum(ref_correct))
            / max(1, len(chal_correct)),
            "truthfulness_score_pp": 100.0
            * (chal_t["truthfulness_score"] - ref_t["truthfulness_score"]),
            "mcnemar_p_value": mc.p_value,
            "mcnemar_method": mc.method,
            "mcnemar_b_ref_only": mc.b,
            "mcnemar_c_challenger_only": mc.c,
            "bootstrap_ci_low": 100.0 * boot.ci_low,
            "bootstrap_ci_high": 100.0 * boot.ci_high,
        }
    out["deltas"] = deltas

    out["per_domain"] = _per_facet_truthfulness(
        questions,
        bare_grades,
        lc_grades,
        surf_grades,
        arms_active=arms_active,
        key_fn=lambda q: q.domain or "(unspecified)",
    )
    out["per_question_type"] = _per_facet_truthfulness(
        questions,
        bare_grades,
        lc_grades,
        surf_grades,
        arms_active=arms_active,
        key_fn=lambda q: q.question_type or "(unspecified)",
    )

    out["grader_methods"] = {
        "bare_llm": _count_methods(bare_grades) if arms_active.get("bare_llm") else {},
        "long_context": _count_methods(lc_grades) if arms_active.get("long_context") else {},
        "surfsense": _count_methods(surf_grades) if arms_active.get("surfsense") else {},
    }
    return out


def _per_facet_truthfulness(
    questions: list[CragRunnerQuestion],
    bare_grades: list[CragGradeResult],
    lc_grades: list[CragGradeResult],
    surf_grades: list[CragGradeResult],
    *,
    arms_active: dict[str, bool],
    key_fn: Any,
) -> dict[str, Any]:
    """Bucket truthfulness scores by ``key_fn(q)``."""

    buckets: dict[str, dict[str, list[CragGradeResult]]] = {}
    for q, b, lc, s in zip(questions, bare_grades, lc_grades, surf_grades, strict=False):
        key = key_fn(q)
        bucket = buckets.setdefault(key, {"bare_llm": [], "long_context": [], "surfsense": []})
        bucket["bare_llm"].append(b)
        bucket["long_context"].append(lc)
        bucket["surfsense"].append(s)
    out: dict[str, Any] = {}
    for key, arms in buckets.items():
        row: dict[str, Any] = {"n": len(arms["bare_llm"])}
        for arm_name, grades in arms.items():
            if not arms_active.get(arm_name):
                continue
            row[arm_name] = _arm_truthfulness(grades)
        out[key] = row
    return out


def _count_methods(grades: list[CragGradeResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for g in grades:
        out[g.method] = out.get(g.method, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Tiny formatting helpers
# ---------------------------------------------------------------------------


def _arm_summary_lines(d: dict[str, Any], *, indent: str) -> str:
    if not d:
        return f"{indent}(no data)"
    acc = d.get("accuracy", 0.0)
    low = d.get("ci_low", 0.0)
    high = d.get("ci_high", 0.0)
    lines = [
        f"{indent}- Accuracy: {acc * 100:.1f}% (Wilson 95% CI: {low * 100:.1f}% – {high * 100:.1f}%)",
        f"{indent}- 3-class: correct={d.get('correct_rate', 0) * 100:.1f}%, "
        f"missing={d.get('missing_rate', 0) * 100:.1f}%, "
        f"incorrect={d.get('incorrect_rate', 0) * 100:.1f}%",
        f"{indent}- Truthfulness score (correct - incorrect)/total: "
        f"{d.get('truthfulness_score', 0) * 100:+.1f}%",
        f"{indent}- Cost / question: ${_dollars(d.get('cost_micros_mean'))} (mean), "
        f"${_dollars(d.get('cost_micros_median'))} (median)",
        f"{indent}- Latency: p50 {_ms_to_s(d.get('latency_ms_median'))}, "
        f"p95 {_ms_to_s(d.get('latency_ms_p95'))}",
    ]
    if d.get("input_tokens_mean") or d.get("output_tokens_mean"):
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


def _pct(value: Any) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "?"


def _signed_pct(value: Any) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "?"


def _fmt(value: Any, ndigits: int) -> str:
    if value is None:
        return "?"
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return "?"


__all__ = ["CragBenchmark", "CragRunnerQuestion"]
