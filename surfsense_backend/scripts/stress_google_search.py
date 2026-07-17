"""Live stress test for the Google Search scraper (REAL solves + proxy spend).

Simulates a burst of concurrent "users" hitting the real ``scrape_serps``
pipeline with a mix of single-query and multi-query requests. Unlike the offline
sim (``scale_google_search.py``), this exercises the actual DataImpulse IPs,
CapSolver solves, and the shared browser — so it surfaces what the sim can't:
real warm-vs-cold latency, whether the warm-IP pool amortizes solves across real
IPs without Google re-walling them, and browser stability under concurrency.

    .venv/Scripts/python.exe scripts/stress_google_search.py --users 30 --gate 8

It COSTS money (each cold IP = one CapSolver solve, bounded by the pool target)
and proxy bandwidth. Metrics are tallied from the live perf/captcha logs.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT / ".env")

# Brand/navigational terms reliably trip the reCAPTCHA wall (a solve/pool grow);
# informational terms are the lighter, often-warm path. A realistic mix.
_BRAND = ["notebooklm", "figma", "notion", "linear app", "vercel", "perplexity ai"]
_INFO = [
    "python asyncio tutorial",
    "best mechanical keyboard 2026",
    "kubernetes vs docker",
    "typescript generics explained",
    "how to make sourdough bread",
    "rust ownership model",
]


class _LogTally(logging.Handler):
    """Counts solves / renders / walls / pool-reuse from the live log stream."""

    _RENDER = re.compile(
        r"has_results=(\w+).*from_pool=(\w+) pool=(\d+)"
    )
    _SOLVE = re.compile(r"\[captcha\] solve (OK|did not)")

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.solves_ok = 0
        self.solves_fail = 0
        self.renders_ok = 0
        self.renders_walled = 0
        self.reuse = 0
        self.grow = 0
        self.max_pool = 0

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        m = self._RENDER.search(msg)
        if m:
            ok, from_pool, pool = m.group(1), m.group(2), int(m.group(3))
            if ok == "True":
                self.renders_ok += 1
            else:
                self.renders_walled += 1
            if from_pool == "True":
                self.reuse += 1
            else:
                self.grow += 1
            self.max_pool = max(self.max_pool, pool)
            return
        s = self._SOLVE.search(msg)
        if s:
            if s.group(1) == "OK":
                self.solves_ok += 1
            else:
                self.solves_fail += 1


def _make_request(rng: random.Random, multi_ratio: float) -> tuple[str, int]:
    """Build one user's request: a single term or a 2-3 term multi-query.
    Returns (newline-joined queries, expected SERP count)."""
    pool = _BRAND + _INFO
    if rng.random() < multi_ratio:
        n = rng.randint(2, 3)
        terms = rng.sample(pool, n)
        return "\n".join(terms), n
    return rng.choice(pool), 1


async def _user(uid: int, queries: str, want: int, results: list[dict]) -> None:
    from app.proprietary.platforms.google_search import (
        GoogleSearchScrapeInput,
        scrape_serps,
    )

    t0 = time.perf_counter()
    inp = GoogleSearchScrapeInput(queries=queries, countryCode="us", languageCode="en")
    try:
        items = await scrape_serps(inp, limit=want)
        got = len(items)
        err = None
    except Exception as e:  # a user request should never crash the whole run
        got, err = 0, repr(e)
    results.append(
        {
            "uid": uid,
            "want": want,
            "got": got,
            "secs": time.perf_counter() - t0,
            "err": err,
        }
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=30, help="concurrent requests")
    ap.add_argument("--gate", type=int, default=8, help="MAX_CONCURRENT_PAGES for run")
    ap.add_argument("--multi-ratio", type=float, default=0.5)
    ap.add_argument("--ramp", type=float, default=0.3, help="secs between user starts")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    # Must be set BEFORE fetch.py is imported (the gate is read at import).
    os.environ["GOOGLE_SEARCH_MAX_CONCURRENT_PAGES"] = str(args.gate)

    logging.basicConfig(level=logging.WARNING)
    tally = _LogTally()
    for name in (
        "app.proprietary.platforms.google_search.fetch",
        "app.proprietary.platforms.google_search.captcha",
    ):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        lg.addHandler(tally)

    from app.proprietary.platforms.google_search.fetch import (  # noqa: E402
        _WARM_POOL_TARGET,
        close_sessions,
    )

    rng = random.Random(args.seed)
    plans = [_make_request(rng, args.multi_ratio) for _ in range(args.users)]
    total_serps = sum(w for _, w in plans)
    n_multi = sum(1 for _, w in plans if w > 1)

    print(f"\n=== LIVE stress: {args.users} users "
          f"({args.users - n_multi} single / {n_multi} multi), "
          f"~{total_serps} SERPs, gate={args.gate}, pool_target={_WARM_POOL_TARGET} ===")
    print("  (real solves + proxy spend; warming up...)\n")

    results: list[dict] = []
    wall0 = time.perf_counter()
    tasks = []
    for uid, (queries, want) in enumerate(plans):
        tasks.append(asyncio.create_task(_user(uid, queries, want, results)))
        await asyncio.sleep(args.ramp)  # gentle ramp, not a thundering herd
    await asyncio.gather(*tasks)
    wall = time.perf_counter() - wall0

    await close_sessions()

    lat = sorted(r["secs"] for r in results)
    got_serps = sum(r["got"] for r in results)
    fails = [r for r in results if r["err"]]
    short = [r for r in results if not r["err"] and r["got"] < r["want"]]

    def pct(p: float) -> float:
        return lat[min(len(lat) - 1, int(p / 100 * len(lat)))] if lat else 0.0

    print("=== results ===")
    print(f"  wall time            = {wall:.0f}s")
    print(f"  requests ok/failed   = {len(results) - len(fails)}/{len(fails)}")
    print(f"  SERPs got/expected   = {got_serps}/{total_serps}"
          + (f"  ({len(short)} short)" if short else ""))
    print(f"  throughput           = {got_serps / wall * 60:.0f} SERP/min")
    print(f"  request latency p50={pct(50):.0f}s  p95={pct(95):.0f}s  "
          f"max={lat[-1] if lat else 0:.0f}s")
    print("  --- pipeline (from live logs) ---")
    print(f"  paid solves ok/fail  = {tally.solves_ok}/{tally.solves_fail}  "
          f"(bounded by pool target {_WARM_POOL_TARGET})")
    print(f"  renders ok/walled    = {tally.renders_ok}/{tally.renders_walled}")
    print(f"  pool reuse/grow      = {tally.reuse}/{tally.grow}  "
          f"(reuse share {100 * tally.reuse / max(1, tally.reuse + tally.grow):.0f}%)")
    print(f"  peak pool size       = {tally.max_pool}")
    if fails:
        print("  --- failures ---")
        for r in fails[:5]:
            print(f"    user{r['uid']}: {r['err']}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
