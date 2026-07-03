# SurfSense proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""Shared primitives for the 03f scorecard: result model, the closure-cell
``page_action`` verdict-extractor (the 03d-shared mechanism), and the scorecard
snapshot writer / baseline-differ / console renderer.

Stdlib-only on purpose (the plan's "no new prod dependency" bar). Everything here
is tolerant: a parse miss yields an ``ERROR`` row, never a crash — detection sites
change their DOM and the harness is manual.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

# Results live next to the harness; screenshots are gitignored, scorecard JSON is
# committed so runs diff against the last baseline (see README + plan §Scorecard).
_PKG_DIR = Path(__file__).resolve().parent
RESULTS_DIR = _PKG_DIR / "results"
SCREENSHOTS_DIR = RESULTS_DIR / "screenshots"


class CheckStatus(StrEnum):
    """Outcome of a single scorecard row."""

    PASS = "PASS"  # met the aspirational bar
    FAIL = "FAIL"  # ran, did not meet the bar
    ERROR = "ERROR"  # could not run / parse (never fatal to the run)
    INFO = "INFO"  # recorded, no pass/fail bar (e.g. TLS JA3, manual links)
    SKIP = "SKIP"  # intentionally not run this invocation


@dataclass
class CheckResult:
    """One row of the scorecard."""

    suite: str  # "S" (stealth) | "E" (extraction)
    name: str  # site / check key
    tier: str  # scrapling-static | scrapling-stealthy | crawl_url | n/a
    status: CheckStatus
    bar: str  # human-readable aspirational threshold
    detail: str = ""  # short human summary of what was observed
    numeric: float | None = None  # comparable metric where one exists
    screenshot: str | None = None  # path, when captured

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class RunMeta:
    """Provenance for a scorecard snapshot so baselines are comparable."""

    timestamp: str
    suites: str
    proxy: str  # masked
    headed: bool
    scrapling_version: str
    captcha_disabled: bool = True
    notes: str = ""

    @staticmethod
    def now(
        *, suites: str, proxy: str | None, headed: bool, scrapling_version: str
    ) -> RunMeta:
        return RunMeta(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            suites=suites,
            proxy=mask_proxy(proxy),
            headed=headed,
            scrapling_version=scrapling_version,
        )


# --- closure-cell page_action (the mechanism shared with 03d) ----------------


@dataclass
class EvalCell:
    """A mutable cell a ``page_action`` writes its ``page.evaluate`` result into.

    Scrapling discards a ``page_action``'s return value, so the only way to get a
    JS-object verdict (CreepJS ``window.Fingerprint``, a Castle.js score node) out
    of the browser is to stash it in a closure variable. This is the exact same
    plumbing 03d's captcha-token injector uses — factored once here.
    """

    value: Any = None
    error: str | None = None
    captured: bool = False


def make_page_action(
    *,
    evaluate_js: str | None = None,
    screenshot_path: str | None = None,
    pre_wait_ms: int = 0,
) -> tuple[Callable[[Any], Any], EvalCell]:
    """Build a sync ``page_action`` + the :class:`EvalCell` it writes into.

    The action (in priority order) optionally sleeps ``pre_wait_ms`` (lets async
    scores settle), optionally evaluates ``evaluate_js`` into the cell, and
    optionally writes a full-page screenshot. Each step is independently guarded
    so one failure (e.g. a site without the JS object) never aborts the fetch.
    Returns the page unchanged (Scrapling re-reads its DOM afterwards).
    """
    cell = EvalCell()

    def _action(page: Any) -> Any:
        if pre_wait_ms > 0:
            with contextlib.suppress(Exception):
                page.wait_for_timeout(pre_wait_ms)
        if evaluate_js is not None:
            try:
                cell.value = page.evaluate(evaluate_js)
                cell.captured = True
            except Exception as exc:
                cell.error = f"{type(exc).__name__}: {exc}"
        if screenshot_path is not None:
            try:
                # The screenshot dir must exist *now* (the page action runs mid-suite,
                # before the end-of-run ``ensure_dirs``); Scrapling/patchright will not
                # create it for us, so a missing dir silently drops every screenshot.
                Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=screenshot_path, full_page=True)
            except Exception as exc:
                if cell.error is None:
                    cell.error = f"screenshot: {type(exc).__name__}: {exc}"
        return page

    return _action, cell


# --- helpers -----------------------------------------------------------------


def mask_proxy(url: str | None) -> str:
    """Mask credentials in a proxy URL for logs/snapshots."""
    if not url:
        return "<none>"
    try:
        p = urlsplit(url)
        host = p.hostname or "?"
        port = f":{p.port}" if p.port else ""
        return f"{p.scheme}://***@{host}{port}"
    except Exception:
        return "<set>"


def ensure_dirs() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def scrapling_version() -> str:
    try:
        import scrapling

        return getattr(scrapling, "__version__", "unknown")
    except Exception:
        return "unavailable"


# --- scorecard I/O -----------------------------------------------------------


def write_scorecard(results: list[CheckResult], meta: RunMeta) -> tuple[Path, Path]:
    """Write the JSON snapshot (committed, baseline) + a readable markdown report.

    The JSON filename is timestamped so prior runs are kept as the baseline trail;
    ``latest.json`` is overwritten as the convenience pointer used by the differ.
    """
    ensure_dirs()
    stamp = meta.timestamp.replace(":", "").replace("-", "")
    payload = {
        "meta": asdict(meta),
        "summary": summarize(results),
        "results": [r.to_row() for r in results],
    }
    json_path = RESULTS_DIR / f"scorecard-{stamp}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (RESULTS_DIR / "latest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    md_path = RESULTS_DIR / f"scorecard-{stamp}.md"
    md_path.write_text(_render_markdown(results, meta), encoding="utf-8")
    return json_path, md_path


def load_last_baseline() -> dict[str, Any] | None:
    """Load the most recent prior scorecard JSON (excluding ``latest.json``)."""
    if not RESULTS_DIR.exists():
        return None
    snaps = sorted(RESULTS_DIR.glob("scorecard-*.json"))
    if not snaps:
        return None
    try:
        return json.loads(snaps[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def summarize(results: list[CheckResult]) -> dict[str, dict[str, int]]:
    """Per-suite ``{passed, failed, error, info, total}`` counts."""
    out: dict[str, dict[str, int]] = {}
    for r in results:
        s = out.setdefault(
            r.suite,
            {"passed": 0, "failed": 0, "error": 0, "info": 0, "skip": 0, "total": 0},
        )
        s["total"] += 1
        key = {
            CheckStatus.PASS: "passed",
            CheckStatus.FAIL: "failed",
            CheckStatus.ERROR: "error",
            CheckStatus.INFO: "info",
            CheckStatus.SKIP: "skip",
        }[r.status]
        s[key] += 1
    return out


def diff_against_baseline(
    results: list[CheckResult], baseline: dict[str, Any] | None
) -> list[str]:
    """Human-readable drift lines comparing this run to the last baseline."""
    if not baseline:
        return ["(no prior baseline — this run becomes the baseline)"]
    prior = {(r["suite"], r["name"]): r for r in baseline.get("results", [])}
    lines: list[str] = []
    for r in results:
        was = prior.get((r.suite, r.name))
        if was is None:
            lines.append(f"+ NEW  [{r.suite}] {r.name}: {r.status.value}")
            continue
        if was["status"] != r.status.value:
            lines.append(f"~ {r.name}: status {was['status']} -> {r.status.value}")
        old_n, new_n = was.get("numeric"), r.numeric
        if old_n is not None and new_n is not None and abs(old_n - new_n) > 1e-9:
            lines.append(f"~ {r.name}: numeric {old_n} -> {new_n}")
    seen = {(r.suite, r.name) for r in results}
    for key, was in prior.items():
        if key not in seen:
            lines.append(f"- GONE [{key[0]}] {key[1]} (was {was['status']})")
    return lines or ["(no changes vs last baseline)"]


# --- rendering ---------------------------------------------------------------

_ICON = {
    CheckStatus.PASS: "PASS",
    CheckStatus.FAIL: "FAIL",
    CheckStatus.ERROR: "ERR ",
    CheckStatus.INFO: "INFO",
    CheckStatus.SKIP: "SKIP",
}


def render_console(results: list[CheckResult]) -> None:
    """Print the grouped scorecard + per-suite totals to stdout."""
    by_suite: dict[str, list[CheckResult]] = {}
    for r in results:
        by_suite.setdefault(r.suite, []).append(r)

    for suite in sorted(by_suite):
        label = (
            "Suite S - stealth/anti-bot"
            if suite == "S"
            else ("Suite E - extraction" if suite == "E" else f"Suite {suite}")
        )
        print(f"\n=== {label} ===")
        for r in by_suite[suite]:
            num = f" [{r.numeric:g}]" if r.numeric is not None else ""
            print(f"  {_ICON[r.status]}  {r.name:<34} {r.tier:<18}{num}")
            if r.detail:
                print(f"         {r.detail}")

    print("\n--- summary ---")
    for suite, s in summarize(results).items():
        print(
            f"  Suite {suite}: {s['passed']}/{s['total']} passed "
            f"(fail={s['failed']} err={s['error']} info={s['info']})"
        )


def _render_markdown(results: list[CheckResult], meta: RunMeta) -> str:
    lines = [
        f"# Crawler scorecard — {meta.timestamp}",
        "",
        f"- proxy: `{meta.proxy}`  headed: `{meta.headed}`  "
        f"captcha-disabled: `{meta.captcha_disabled}`",
        f"- scrapling: `{meta.scrapling_version}`  suites: `{meta.suites}`",
        "",
        "| Suite | Check | Tier | Status | Numeric | Detail |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        num = "" if r.numeric is None else f"{r.numeric:g}"
        detail = r.detail.replace("|", "\\|")
        lines.append(
            f"| {r.suite} | {r.name} | {r.tier} | {r.status.value} | {num} | {detail} |"
        )
    lines.append("")
    for suite, s in summarize(results).items():
        lines.append(
            f"- **Suite {suite}**: {s['passed']}/{s['total']} passed "
            f"(fail={s['failed']}, err={s['error']}, info={s['info']})"
        )
    return "\n".join(lines) + "\n"
