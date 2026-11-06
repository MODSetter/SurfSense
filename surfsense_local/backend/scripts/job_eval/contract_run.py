"""One eval run of a contract case: the app's runner over the real contract and playbook, the
redlined copy it makes, and the record a report rolls up."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from job_eval.contract_cases import ContractCase
from job_eval.contract_integrity import contract_problems
from job_eval.contract_score import score_review
from job_eval.source_files import source_text

from modules.artifacts.revised_copies.engines import word
from modules.jobs.word_clauses.config import ClauseConfig
from modules.jobs.word_clauses.report import RUNNER
from modules.jobs.word_clauses.review import review_contract


def run_contract_case(
    out: Path,
    spec: str,
    case: ContractCase,
    config: ClauseConfig,
    number: int,
    *,
    model,
    checker=None,
    settings: dict[str, bool],
    embed=None,
    options: dict,
) -> dict:
    """`options` are the run's command-line choices, kept in its record."""
    sources = [source_text(path, index + 1) for index, path in enumerate(case.sources)]
    gold_points = {g.point for g in case.gold}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    named = spec + (f"-checked-{options.get('checker')}" if checker else "")
    folder = (
        out / f"{stamp}-{case.id}-{named.replace(':', '_').replace('/', '_')}-r{number}"
    )
    folder.mkdir(parents=True)
    print(f"{case.id} on {spec}, run {number}: {folder.name}", flush=True)
    started = time.monotonic()
    review = review_contract(
        case.contract,
        sources,
        config,
        model,
        only=lambda point: point.key in gold_points,
        on_row=lambda done, total: print(f"  {done}/{total}", flush=True),
        embed=embed,
        checker=checker,
        settings=settings,
    )
    revised = folder / "redlined.docx"
    applied = word.apply(case.contract, review.operations, revised)
    scored = score_review(case, review.results)
    integrity = (
        contract_problems(case.contract, revised)
        if applied.saved
        else ["the engine saved nothing: " + applied.as_text()]
    )
    record = {
        "kind": "contract",
        "runner": RUNNER,
        "case": case.id,
        "title": case.title,
        "gold_status": case.gold_status,
        "model": spec,
        "checker": options.get("checker"),
        "run": number,
        "started": stamp,
        "seconds": round(time.monotonic() - started, 1),
        "settings": {**options, "job": review.settings},
        "whole_sources": review.whole_sources,
        "whole_contract": review.whole_contract,
        "counts": review.counts,
        "scored_points": len(scored.points),
        "correct": scored.correct,
        "outcome_correct": scored.outcome_correct,
        "changes": scored.changes,
        "located": list(scored.located),
        "integrity": integrity,
        "misses": scored.confusion(),
        "spend": _spend(model, checker),
        "points": [p.__dict__ for p in scored.points],
        "answers": [
            {
                "key": r.point.key,
                "said": r.said,
                "verdict": r.verdict,
                "paragraphs": r.paragraphs,
                "quote": r.quote,
                "change": None
                if r.change is None
                else {
                    "kind": r.change.kind,
                    "clause": review.contract.clauses[r.change.clause].id,
                    "new": r.change.new_text,
                },
                "codes": r.codes,
                "why": r.why,
                "internal": r.internal,
            }
            for r in review.results
        ],
    }
    (folder / "run.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    changes = scored.changes
    found, of = scored.located
    print(
        f"  verdicts {scored.correct}/{len(scored.points)}, outcomes "
        f"{scored.outcome_correct}/{len(scored.points)}, changes right {changes['right']} "
        f"unneeded {changes['unneeded']} missed {changes['missed']}, clause found "
        f"{found}/{of}, for a person {review.counts['for_person']}, integrity problems "
        f"{len(integrity)}, ${record['spend']['dollars']:.4f}, {record['seconds']}s",
        flush=True,
    )
    return record


def _spend(model, checker) -> dict:
    spent = {
        "calls": model.spend.calls,
        "input_tokens": model.spend.input_tokens,
        "cached_tokens": model.spend.cached_tokens,
        "output_tokens": model.spend.output_tokens,
        "dollars": round(
            model.spend.dollars + (checker.spend.dollars if checker else 0.0), 4
        ),
        "errors": model.spend.errors[:20],
        "providers": dict(model.spend.providers),
    }
    if checker:
        spent["checker_calls"] = checker.spend.calls
    return spent
