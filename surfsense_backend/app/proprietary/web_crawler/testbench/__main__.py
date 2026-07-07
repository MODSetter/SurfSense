# SurfSense proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""CLI for the 03f manual scorecard. Run from the backend directory:

    uv run python -m app.proprietary.web_crawler.testbench --suite all
    uv run python -m app.proprietary.web_crawler.testbench --suite S --headed
    uv run python -m app.proprietary.web_crawler.testbench --suite E --no-screenshots

Mirrors CloakBrowser's ``bin/cloaktest`` ergonomics. Writes a timestamped
scorecard (JSON + markdown) under ``results/`` and diffs against the last
baseline. Captcha solving is forced OFF so the scorecard measures the *unaided*
stealth ceiling (03f §Harness).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# --- bootstrap: load .env + put backend root on sys.path BEFORE importing app.* ---
# __file__ = app/proprietary/web_crawler/testbench/__main__.py -> backend root is 4 up.
_BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
for _candidate in (_BACKEND_ROOT / ".env", _BACKEND_ROOT.parent / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break

# Force captcha solving OFF: Suite S measures the unaided score and we never want
# the 03d injector firing paid solves against the reCAPTCHA-demo row. Must be set
# before app.config is imported (config snapshots env at import).
os.environ["CAPTCHA_SOLVING_ENABLED"] = "false"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m app.proprietary.web_crawler.testbench",
        description="Manual undetectability & extraction scorecard (Phase 3f).",
    )
    p.add_argument(
        "--suite",
        choices=["S", "E", "all"],
        default="all",
        help="S=stealth/anti-bot, E=extraction correctness, all=both.",
    )
    p.add_argument(
        "--proxy",
        default=None,
        help="Override proxy URL for Suite S (default: the app proxy provider).",
    )
    p.add_argument(
        "--headed",
        action="store_true",
        help="Run the browser tier headful (headless=False).",
    )
    p.add_argument(
        "--no-screenshots",
        action="store_true",
        help="Skip per-site screenshots (faster, no results/screenshots writes).",
    )
    return p.parse_args(argv)


async def _amain(args: argparse.Namespace) -> int:
    # Imports happen here (after bootstrap + env override) so app.config sees the
    # forced CAPTCHA_SOLVING_ENABLED=false and the resolved .env.
    from app.utils.proxy import get_proxy_url

    from .core import (
        RunMeta,
        diff_against_baseline,
        load_last_baseline,
        render_console,
        scrapling_version,
        write_scorecard,
    )

    proxy = args.proxy or get_proxy_url()
    screenshots = not args.no_screenshots
    results = []

    print(
        f"== crawler scorecard == suite={args.suite} "
        f"headed={args.headed} proxy={'set' if proxy else 'NONE'} "
        f"screenshots={screenshots}"
    )
    if not proxy:
        print(
            "  WARNING: no proxy configured — the hard anti-bot rows are expected "
            "to fail from a datacenter IP (see README)."
        )

    baseline = load_last_baseline()

    if args.suite in ("S", "all"):
        from .suite_stealth import run_suite_s

        results += await run_suite_s(
            proxy=proxy, headed=args.headed, screenshots=screenshots
        )

    if args.suite in ("E", "all"):
        from .suite_extraction import run_suite_e

        results += await run_suite_e()

    render_console(results)

    meta = RunMeta.now(
        suites=args.suite,
        proxy=proxy,
        headed=args.headed,
        scrapling_version=scrapling_version(),
    )
    json_path, md_path = write_scorecard(results, meta)

    print("\n--- drift vs last baseline ---")
    for line in diff_against_baseline(results, baseline):
        print(f"  {line}")

    print(f"\nscorecard JSON: {json_path}")
    print(f"scorecard MD:   {md_path}")
    return 0


def main() -> None:
    args = _parse_args(sys.argv[1:])
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
