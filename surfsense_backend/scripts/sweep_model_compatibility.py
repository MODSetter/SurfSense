"""CLI for the model compatibility sweep.

Probes every catalogue model through three escalating stages and records
whether it can actually serve a turn. The probes themselves live in
``app/services/model_compatibility_sweep.py`` so the periodic Celery task runs
exactly the same code; this file is argument parsing and output.

Usage::

    python -m scripts.sweep_model_compatibility --dry-run   # list targets, no calls
    python -m scripts.sweep_model_compatibility             # sweep unchecked models
    python -m scripts.sweep_model_compatibility --recheck   # re-probe everything
    python -m scripts.sweep_model_compatibility --model anthropic/claude-sonnet-4.5

Resumable: models with a verdict newer than ``--max-age-days`` are skipped, so
an interrupted sweep continues where it stopped. Live-provider script, kept out
of CI. Each probed model costs a handful of tokens.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

import litellm  # noqa: E402

from app.services.model_compatibility import (  # noqa: E402
    CompatibilityStatus,
    CompatibilityVerdict,
)
from app.services.model_compatibility_sweep import (  # noqa: E402
    DEFAULT_CONCURRENCY,
    DEFAULT_MAX_AGE_DAYS,
    fetch_catalogue_model_ids,
    recently_checked_ids,
    resolve_api_key,
    sweep_models,
)


def _report(model_id: str, verdict: CompatibilityVerdict) -> None:
    if verdict.status is CompatibilityStatus.OK:
        return
    print(
        f"  {verdict.status.value.upper():<7} {model_id} "
        f"[{verdict.failure_stage}] {verdict.error_code} "
        f"{(verdict.error_excerpt or '')[:100]}"
    )


async def run(args: argparse.Namespace) -> int:
    api_key = resolve_api_key()
    if not api_key:
        print("No OpenRouter API key (set OPENROUTER_API_KEY).")
        return 2

    model_ids = await fetch_catalogue_model_ids()
    if args.model:
        wanted = set(args.model)
        # Probe explicitly named ids even when a filter already excludes them,
        # which is what makes this usable to confirm a suspected bad model.
        model_ids = [m for m in model_ids if m in wanted] + sorted(
            wanted - set(model_ids)
        )

    skipped = 0
    if not args.recheck:
        fresh = await recently_checked_ids(args.max_age_days)
        skipped = sum(1 for m in model_ids if m in fresh)
        model_ids = [m for m in model_ids if m not in fresh]

    if args.limit:
        model_ids = model_ids[: args.limit]

    print(
        f"targets: {len(model_ids)} | skipped as fresh: {skipped} | "
        f"concurrency: {args.concurrency}"
    )
    if args.dry_run:
        for model_id in model_ids[:20]:
            print(f"  {model_id}")
        if len(model_ids) > 20:
            print(f"  ... and {len(model_ids) - 20} more")
        return 0

    counts = await sweep_models(
        model_ids,
        api_key=api_key,
        concurrency=args.concurrency,
        on_verdict=_report,
    )
    print("\ndone: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="List targets without calling providers."
    )
    parser.add_argument(
        "--recheck",
        action="store_true",
        help="Re-probe models that already have a recent verdict.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help="Treat verdicts newer than this as fresh and skip them.",
    )
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--limit", type=int, default=0, help="Probe at most N models.")
    parser.add_argument(
        "--model", action="append", default=[], help="Probe only these model ids."
    )
    args = parser.parse_args()

    litellm.suppress_debug_info = True
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
