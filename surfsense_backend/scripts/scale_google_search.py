"""Zero-cost concurrency simulation for the Google Search fetch seam.

Drives many concurrent ``fetch_serp_html`` calls with the network I/O stubbed
out (no live Google, no proxy spend, no captcha solves) so we can measure the
*structure* of the scraper under load without paying for it:

* **throughput** — completions/sec at steady state (the per-process ceiling is
  the render gate divided by warm-render latency; nothing above it is real),
* **latency** — p50/p95/p99 wait as the gate queues excess renders,
* **solves** — how many paid solves the run would cost (the number we most want
  the sticky-IP pool to shrink), and
* **per-IP peak concurrency** — the funneling metric: how many renders pile onto
  a single sticky IP at once (a hot IP is what Google re-walls).

The stub keeps the *real* ``fetch_serp_html`` loop intact (sticky reuse,
exemption skip-precheck, the render gate, inflight accounting) and only replaces
``_precheck`` / ``_get_session`` / ``get_proxy_url``. Timings are compressed
(warm≈0.1 s vs ~14 s live) and extrapolated to real seconds via the warm-render
ratio, since the system is gate-bounded sleeps + a semaphore (delays scale
linearly).

    .venv/Scripts/python.exe scripts/scale_google_search.py --count 400 --rate 60
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from app.proprietary.platforms.google_search import fetch  # noqa: E402

# Live-measured render latencies (README "Timings"); used only to translate the
# compressed sim clock back to real seconds for the human-readable report.
_REAL_WARM_S = 14.0
_REAL_SOLVE_S = 45.0

_RESULTS_HTML = '<div id="rso">ok</div>'  # trips fetch._has_results


class _Metrics:
    """Browser-loop-side counters (fetch runs on two loops → guard with a lock)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.solves = 0
        self.renders = 0
        self.ip_hits: dict[str, int] = {}
        self.ip_now: dict[str, int] = {}
        self.ip_peak: dict[str, int] = {}

    def enter(self, proxy: str, solved: bool) -> None:
        with self.lock:
            self.renders += 1
            if solved:
                self.solves += 1
            self.ip_hits[proxy] = self.ip_hits.get(proxy, 0) + 1
            n = self.ip_now.get(proxy, 0) + 1
            self.ip_now[proxy] = n
            self.ip_peak[proxy] = max(self.ip_peak.get(proxy, 0), n)

    def exit(self, proxy: str) -> None:
        with self.lock:
            self.ip_now[proxy] = self.ip_now.get(proxy, 1) - 1


class _FakePage:
    def __init__(self) -> None:
        self.status = 200
        self.html_content = _RESULTS_HTML


class _FakeSession:
    """Stands in for AsyncStealthySession: sleeps like a render, simulates the
    solve on a cold IP by seeding fetch._exemption_jar (what page_action does)."""

    def __init__(self, metrics: _Metrics, warm_s: float, solve_s: float) -> None:
        self.m = metrics
        self.warm_s = warm_s
        self.solve_s = solve_s

    async def fetch(self, url, proxy=None, **kwargs):
        key = proxy or ""
        # Cold IP (no cached exemption) pays the solve and warms the jar; a warm
        # IP just pays the render. Mirrors _make_page_action's cache write.
        cold = key not in fetch._exemption_jar
        self.m.enter(key, solved=cold)
        try:
            if cold:
                await asyncio.sleep(self.solve_s)
                fetch._exemption_jar[key] = [{"name": "GOOGLE_ABUSE_EXEMPTION"}]
            await asyncio.sleep(self.warm_s)
            return _FakePage()
        finally:
            self.m.exit(key)


def _install_stubs(metrics: _Metrics, warm_s: float, solve_s: float, precheck_s: float):
    base = "http://u:p@gw.dataimpulse.com:823"  # hostname in fetch._STICKY_HOSTS
    session = _FakeSession(metrics, warm_s, solve_s)

    async def fake_precheck(url, proxy):
        await asyncio.sleep(precheck_s)
        return True

    async def fake_get_session(mobile):
        return session

    fetch.get_proxy_url = lambda: base
    fetch._precheck = fake_precheck
    fetch._get_session = fake_get_session
    fetch.captcha_enabled = lambda: True
    fetch.get_captcha_config = lambda: object()
    fetch._captcha.solver_latched = lambda: False
    # The pool's backpressure poll is negligible vs a real 14 s render; keep it
    # proportional under the compressed sim clock so waiters don't idle.
    fetch._POOL_WAIT_S = max(warm_s * 0.05, 0.001)

    # Isolate the sim to the LOCAL pool: the cross-process store (Redis) has its
    # own unit test and would otherwise add ping latency / cross-run bleed here.
    async def _no_adopt(exclude):
        return None

    async def _noop(*a, **k):
        return None

    fetch._store.adopt = _no_adopt
    fetch._store.publish = _noop
    fetch._store.evict = _noop


def _reset_state() -> None:
    fetch._exemption_jar.clear()
    for name in ("_pool", "_pool_inflight"):
        obj = getattr(fetch, name, None)
        if isinstance(obj, dict):
            obj.clear()
    if hasattr(fetch, "_pool_pending"):
        fetch._pool_pending = 0
    if hasattr(fetch, "_last_good_proxy"):  # pre-pool revision
        fetch._last_good_proxy = None


async def _drive(count: int, rate: float) -> list[float]:
    """Fire ``count`` fetches at ``rate``/sec (steady arrival), return latencies."""
    lat: list[float] = []
    interval = 1.0 / rate if rate > 0 else 0.0

    async def one() -> None:
        t0 = time.perf_counter()
        await fetch.fetch_serp_html("https://www.google.com/search?q=notebooklm")
        lat.append(time.perf_counter() - t0)

    tasks: list[asyncio.Task] = []
    for _ in range(count):
        tasks.append(asyncio.create_task(one()))
        if interval:
            await asyncio.sleep(interval)
    await asyncio.gather(*tasks)
    return lat


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=400)
    ap.add_argument("--rate", type=float, default=60.0, help="arrivals/sec (sim clock)")
    ap.add_argument(
        "--warm", type=float, default=0.10, help="warm render seconds (sim)"
    )
    ap.add_argument("--solve", type=float, default=0.45, help="solve seconds (sim)")
    ap.add_argument("--precheck", type=float, default=0.01)
    args = ap.parse_args()

    metrics = _Metrics()
    _install_stubs(metrics, args.warm, args.solve, args.precheck)
    _reset_state()

    scale = _REAL_WARM_S / args.warm  # sim seconds → real seconds
    gate = fetch._MAX_CONCURRENT_PAGES
    pool = getattr(fetch, "_WARM_POOL_TARGET", None)

    wall0 = time.perf_counter()
    lat = await _drive(args.count, args.rate)
    wall = time.perf_counter() - wall0
    await fetch._in_browser_loop(asyncio.sleep(0))  # let last exit() settle

    hot_peak = max(metrics.ip_peak.values()) if metrics.ip_peak else 0
    top_hits = max(metrics.ip_hits.values()) if metrics.ip_hits else 0
    top_share = 100.0 * top_hits / metrics.renders if metrics.renders else 0.0
    thru_sim = args.count / wall if wall else 0.0
    thru_real = thru_sim / scale

    print("\n=== Google Search scale simulation ===")
    print(
        f"  gate (_MAX_CONCURRENT_PAGES) = {gate}"
        + (f", warm-pool target = {pool}" if pool else "  (single-slot sticky IP)")
    )
    print(f"  requests={args.count} arrival_rate={args.rate}/s (sim)")
    print("  --- structure (scale-free) ---")
    print(
        f"  paid solves           = {metrics.solves}  (want ~pool size, not ~requests)"
    )
    print(f"  distinct sticky IPs   = {len(metrics.ip_hits)}")
    print(
        f"  busiest IP carried    = {top_hits}/{metrics.renders} renders "
        f"({top_share:.0f}%)  (funneling; want ~even spread)"
    )
    print(f"  peak renders on 1 IP  = {hot_peak}  (concurrency; capped by gate)")
    print(
        f"  --- throughput / latency (extrapolated to live @ warm={_REAL_WARM_S}s) ---"
    )
    print(f"  throughput  = {thru_real * 60:.0f} SERP/min  ({thru_real:.2f}/s)")
    print(
        f"  latency p50 = {_pct(lat, 50) * scale:6.1f}s   p95 = {_pct(lat, 95) * scale:6.1f}s   "
        f"p99 = {_pct(lat, 99) * scale:6.1f}s"
    )
    print(
        f"  ceiling (gate/warm) = {gate / _REAL_WARM_S * 60:.0f} SERP/min per process"
    )
    need = 500 / (gate / _REAL_WARM_S * 60)
    print(
        f"  -> to sustain 500 SERP/min you need ~{need:.0f} such processes "
        f"(or a larger gate)\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
