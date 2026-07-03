# SurfSense proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""Suite S — stealth / anti-bot scorecard.

Drives the **browser tier** (``StealthyFetcher``) against the standard
bot-detection sites and the **HTTP tier** (``AsyncFetcher``) against the TLS /
proxy-leak JSON endpoints. Critically, the browser tier is built from the **same
centralized stealth builder the crawler ships** (``build_stealthy_kwargs`` /
``get_stealth_config`` in ``app/proprietary/web_crawler/stealth.py``) so the scorecard grades
the exact browser we run in production — no test-vs-prod drift (03f §Harness).

Verdict extraction is best-effort and tolerant: machine-readable signals
(reCAPTCHA score text, are-you-a-bot text, sannysoft failed-cell count, TLS/proxy
JSON) get a real PASS/FAIL/numeric; DOM-heavy fingerprint pages are recorded as
INFO with a screenshot + captured text for the operator to read. Tightening any
parser later is a one-function change (the spec list is the extension point).
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scrapling.fetchers import AsyncFetcher, StealthyFetcher

from app.proprietary.web_crawler.stealth import (
    build_stealthy_kwargs,
    get_stealth_config,
)

from .core import (
    SCREENSHOTS_DIR,
    CheckResult,
    CheckStatus,
    EvalCell,
    make_page_action,
)

# Parser: (page, eval_cell) -> (status, numeric, detail).
Parser = Callable[[Any, EvalCell], "tuple[CheckStatus, float | None, str]"]


@dataclass
class StealthSite:
    """One browser-tier detection site + how to read its verdict."""

    name: str
    url: str
    bar: str
    parse: Parser
    settle_ms: int = 0  # extra in-page wait for async-computed scores
    evaluate_js: str | None = None  # for window.* / JS-object verdicts


def _text(page: Any, limit: int = 4000) -> str:
    """Best-effort visible text of a fetched page (short, for fallback details)."""
    return _full_text(page, limit)


def _full_text(page: Any, limit: int = 200_000) -> str:
    """Untruncated visible text — detector verdicts live deep in long pages."""
    try:
        txt = page.get_all_text()
        if txt:
            return str(txt)[:limit]
    except Exception:
        pass
    try:
        return str(page.html_content or "")[:limit]
    except Exception:
        return ""


# --- per-site parsers (all written against real DOM dumps, no screenshots) ---


def _parse_sannysoft(page: Any, _cell: EvalCell):
    """Count failed result cells (JS sets class='failed' on red rows)."""
    html = ""
    with contextlib.suppress(Exception):
        html = page.html_content or ""
    fails = len(re.findall(r'class="[^"]*\bfailed\b[^"]*"', html))
    if not html:
        return (CheckStatus.ERROR, None, "no html returned")
    status = CheckStatus.PASS if fails == 0 else CheckStatus.FAIL
    return (status, float(fails), f"{fails} failed cell(s) (bar: 0)")


# deviceandbrowserinfo renders a JSON verdict block: {"isBot": false, ...}.
_ISBOT_RE = re.compile(r'"isbot"\s*:\s*(true|false)', re.IGNORECASE)


def _parse_areyouabot(page: Any, _cell: EvalCell):
    txt = _full_text(page)
    m = _ISBOT_RE.search(txt)
    if m:
        is_bot = m.group(1).lower() == "true"
        return (
            CheckStatus.FAIL if is_bot else CheckStatus.PASS,
            1.0 if is_bot else 0.0,
            f"isBot={is_bot}",
        )
    low = txt.lower()
    if "you are human" in low or "not a bot" in low:
        return (CheckStatus.PASS, 0.0, "verdict: human")
    if "you are a bot" in low:
        return (CheckStatus.FAIL, 1.0, "verdict: BOT")
    return (CheckStatus.INFO, None, f"unparsed: {low[:120]!r}")


# The reCAPTCHA demo echoes the server verify response: {"success":true,"score":0.9}.
_SCORE_JSON_RE = re.compile(r'"score"\s*:\s*([0-9]*\.?[0-9]+)')


def _parse_recaptcha_v3(page: Any, _cell: EvalCell):
    txt = _full_text(page)
    m = _SCORE_JSON_RE.search(txt)
    if not m:  # fall back to looser prose match
        m = re.search(r"score[^0-9]{0,12}([01](?:\.\d+)?)", txt, re.IGNORECASE)
    if not m:
        return (CheckStatus.INFO, None, f"no score parsed: {txt[:120]!r}")
    score = float(m.group(1))
    status = CheckStatus.PASS if score >= 0.7 else CheckStatus.FAIL
    return (status, score, f"reCAPTCHA v3 score={score} (bar: >=0.7)")


# CreepJS prints category percentages ("33% headless") + boolean tells inline.
_CREEPJS_TELLS = (
    "webDriverIsOn",
    "hasHeadlessUA",
    "hasHeadlessWorkerUA",
    "hasBadWebGL",
    "hasSwiftShader",
)


def _parse_creepjs(page: Any, _cell: EvalCell):
    """Grade CreepJS by its headless-similarity % + the boolean spoof tells."""
    txt = _full_text(page)

    def _pct(label: str) -> int | None:
        m = re.search(r"(\d+)%\s*" + label, txt, re.IGNORECASE)
        return int(m.group(1)) if m else None

    headless = _pct(r"headless")
    stealth = _pct(r"stealth")
    tells = [
        flag
        for flag in _CREEPJS_TELLS
        if re.search(re.escape(flag) + r"\s*:\s*true", txt, re.IGNORECASE)
    ]
    if headless is None and not tells:
        return (CheckStatus.INFO, None, f"unparsed: {txt[:120]!r}")
    bad = bool(tells) or (headless is not None and headless > 30)
    detail = f"headless={headless}% stealth={stealth}% tells={tells or 'none'}"
    return (
        CheckStatus.FAIL if bad else CheckStatus.PASS,
        float(headless) if headless is not None else None,
        detail,
    )


# incolumitas emits JSON test blocks ("WEBDRIVER":"FAIL") + an IP classification.
_FAIL_KEY_RE = re.compile(r'"([A-Za-z_]+)"\s*:\s*"FAIL"')
_DC_RE = re.compile(r'"is_datacenter"\s*:\s*(true|false)', re.IGNORECASE)
_BEHAV_RE = re.compile(r"Your Behavioral Score:\s*([0-9.]+)", re.IGNORECASE)


def _parse_incolumitas(page: Any, _cell: EvalCell):
    txt = _full_text(page)
    fails = sorted(set(_FAIL_KEY_RE.findall(txt)))
    dc = _DC_RE.search(txt)
    datacenter = dc.group(1) if dc else "?"
    behav = _BEHAV_RE.search(txt)
    bscore = behav.group(1) if behav else "n/a (no synthetic input)"
    if not fails and dc is None:
        return (CheckStatus.INFO, None, f"unparsed: {txt[:120]!r}")
    detail = (
        f"fpscanner FAIL={fails or 'none'} datacenter={datacenter} behavioral={bscore}"
    )
    return (
        CheckStatus.PASS if not fails else CheckStatus.FAIL,
        float(len(fails)),
        detail,
    )


# fingerprint-scan.com: "Bot Risk Score: 35/100"; the site flags >50 as bot.
_RISK_RE = re.compile(r"Bot Risk Score:\s*(\d+)\s*/\s*100", re.IGNORECASE)


def _parse_fingerprint_scan(page: Any, _cell: EvalCell):
    txt = _full_text(page)
    m = _RISK_RE.search(txt)
    if not m:
        return (CheckStatus.INFO, None, f"no risk score: {txt[:120]!r}")
    score = int(m.group(1))
    status = CheckStatus.PASS if score < 50 else CheckStatus.FAIL
    return (status, float(score), f"bot risk {score}/100 (bar: <50)")


def _parse_fingerprintjs(page: Any, _cell: EvalCell):
    """FingerprintJS Pro Smart Signals: a block message means we were detected."""
    low = _full_text(page).lower()
    if "access denied" in low or "tampering detected" in low:
        return (CheckStatus.FAIL, 1.0, "blocked: anti-detect tampering / access denied")
    if "search for today's flights" in low or "flight" in low:
        return (CheckStatus.PASS, 0.0, "not blocked (flight results served)")
    return (CheckStatus.INFO, None, f"unparsed: {low[:120]!r}")


def _parse_browserscan(page: Any, _cell: EvalCell):
    """BrowserScan grades each probe Normal/Abnormal; any Abnormal = detected."""
    txt = _full_text(page)
    abnormal = len(re.findall(r"\bAbnormal\b", txt))
    if abnormal == 0 and "Test Results:" in txt and "Normal" in txt:
        return (CheckStatus.PASS, 0.0, "Test Results: Normal (0 Abnormal)")
    if abnormal > 0:
        return (CheckStatus.FAIL, float(abnormal), f"{abnormal} Abnormal signal(s)")
    return (CheckStatus.INFO, None, f"unparsed: {txt[:120]!r}")


# The scrapingcourse CF canary prints an explicit success line once solved; a
# failure leaves the interstitial ("Just a moment...") in the DOM. This is the
# ONLY site here that exercises solve_cloudflare (the others present no challenge).
_CF_PASS = "you bypassed the cloudflare challenge"
_CF_BLOCK = ("just a moment", "attention required", "verify you are human")


def _parse_cloudflare(page: Any, _cell: EvalCell):
    low = _full_text(page).lower()
    if _CF_PASS in low:
        return (CheckStatus.PASS, 0.0, "bypassed Cloudflare challenge")
    if any(m in low for m in _CF_BLOCK):
        return (CheckStatus.FAIL, 1.0, "stuck on Cloudflare interstitial")
    return (CheckStatus.INFO, None, f"unparsed: {low[:120]!r}")


# iphey renders a masthead verdict "Your Digital Identity Looks <Trustworthy|
# Unreliable|Suspicious>" after an async fingerprint+IP correlation (slow → big
# settle). Only "Trustworthy" is a clean pass.
_IPHEY_RE = re.compile(r"Your Digital Identity Looks\s+([A-Za-z]+)", re.IGNORECASE)


def _parse_iphey(page: Any, _cell: EvalCell):
    txt = _full_text(page)
    m = _IPHEY_RE.search(txt)
    if not m:
        return (CheckStatus.INFO, None, f"verdict not loaded: {txt[:120]!r}")
    verdict = m.group(1)
    ok = verdict.lower() == "trustworthy"
    return (
        CheckStatus.PASS if ok else CheckStatus.FAIL,
        0.0 if ok else 1.0,
        f"iphey verdict: {verdict}",
    )


_BROWSER_SITES: list[StealthSite] = [
    StealthSite(
        name="sannysoft",
        url="https://bot.sannysoft.com/",
        bar="0 failed cells",
        parse=_parse_sannysoft,
        settle_ms=3000,
    ),
    StealthSite(
        name="deviceandbrowserinfo",
        url="https://deviceandbrowserinfo.com/are_you_a_bot",
        bar="isBot=false",
        parse=_parse_areyouabot,
        settle_ms=3000,
    ),
    StealthSite(
        name="recaptcha_v3_score",
        url="https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php",
        bar="score >= 0.7",
        parse=_parse_recaptcha_v3,
        # v3 runs grecaptcha.execute then round-trips a server verify; too-short a
        # wait reads the page before the {"score":..} JSON lands (false 0.0).
        settle_ms=12000,
    ),
    StealthSite(
        name="creepjs",
        url="https://abrahamjuliot.github.io/creepjs/",
        bar="headless <=30%, no spoof tells",
        parse=_parse_creepjs,
        settle_ms=30000,
    ),
    StealthSite(
        name="browserscan",
        url="https://www.browserscan.net/bot-detection",
        bar="0 Abnormal",
        parse=_parse_browserscan,
        settle_ms=8000,
    ),
    StealthSite(
        name="incolumitas",
        url="https://bot.incolumitas.com/",
        bar="0 fpscanner FAIL",
        parse=_parse_incolumitas,
        settle_ms=12000,
    ),
    StealthSite(
        name="fingerprint_scan",
        url="https://fingerprint-scan.com/",
        bar="bot risk < 50/100",
        parse=_parse_fingerprint_scan,
        settle_ms=20000,
    ),
    StealthSite(
        name="fingerprintjs_demo",
        url="https://demo.fingerprint.com/web-scraping",
        bar="not blocked",
        parse=_parse_fingerprintjs,
        settle_ms=6000,
    ),
    StealthSite(
        name="cloudflare_challenge",
        url="https://www.scrapingcourse.com/cloudflare-challenge",
        bar="bypass CF challenge (exercises solve_cloudflare)",
        parse=_parse_cloudflare,
        settle_ms=15000,
    ),
    StealthSite(
        name="iphey",
        url="https://iphey.com/",
        bar="verdict Trustworthy",
        parse=_parse_iphey,
        # iphey's verdict loads via a slow async correlation; <~20s reads the
        # "Temporary value" placeholder (false INFO).
        settle_ms=25000,
    ),
]

# S2 — per-property fingerprint pages: too visual to auto-grade; emit as manual
# links so the operator can confirm the 03e levers (canvas/webgl/fonts/webrtc).
_MANUAL_LINKS: list[tuple[str, str]] = [
    ("browserleaks_canvas", "https://browserleaks.com/canvas"),
    ("browserleaks_webgl", "https://browserleaks.com/webgl"),
    ("browserleaks_fonts", "https://browserleaks.com/fonts"),
    ("browserleaks_webrtc", "https://browserleaks.com/webrtc"),
]


def _run_browser_site(
    site: StealthSite, *, proxy: str | None, headed: bool, screenshots: bool
) -> CheckResult:
    shot = str(SCREENSHOTS_DIR / f"S_{site.name}.png") if screenshots else None
    action, cell = make_page_action(
        evaluate_js=site.evaluate_js,
        screenshot_path=shot,
        pre_wait_ms=site.settle_ms,
    )
    kwargs: dict[str, Any] = {
        "headless": not headed,
        "network_idle": True,
        "block_ads": True,
        "solve_cloudflare": True,
        "proxy": proxy,
        "timeout": 120000,
        "page_action": action,
    }
    # Single source of truth — the exact levers the production crawler ships.
    kwargs.update(build_stealthy_kwargs(get_stealth_config()))

    try:
        page = StealthyFetcher.fetch(site.url, **kwargs)
    except Exception as exc:
        return CheckResult(
            suite="S",
            name=site.name,
            tier="scrapling-stealthy",
            status=CheckStatus.ERROR,
            bar=site.bar,
            detail=f"fetch failed: {type(exc).__name__}: {exc}",
            screenshot=shot,
        )

    try:
        status, numeric, detail = site.parse(page, cell)
    except Exception as exc:
        status, numeric, detail = (
            CheckStatus.ERROR,
            None,
            f"parse failed: {type(exc).__name__}: {exc}",
        )
    return CheckResult(
        suite="S",
        name=site.name,
        tier="scrapling-stealthy",
        status=status,
        bar=site.bar,
        detail=detail,
        numeric=numeric,
        screenshot=shot,
    )


async def _run_tls(proxy: str | None) -> CheckResult:
    """S3 — JA3/JA4/PeetPrint of the impersonated static (curl_cffi) tier."""
    try:
        page = await AsyncFetcher.get(
            "https://tls.peet.ws/api/all",
            stealthy_headers=True,
            impersonate="chrome",
            proxy=proxy,
            timeout=30,
        )
        data = page.json()
        tls = data.get("tls", {}) if isinstance(data, dict) else {}
        ja3 = tls.get("ja3_hash") or tls.get("ja3")
        ja4 = tls.get("ja4")
        peet = tls.get("peetprint_hash")
        return CheckResult(
            suite="S",
            name="tls_fingerprint",
            tier="scrapling-static",
            status=CheckStatus.INFO,
            bar="informational (diff vs real Chrome)",
            detail=f"ja3={ja3} ja4={ja4} peet={peet}",
        )
    except Exception as exc:
        return CheckResult(
            suite="S",
            name="tls_fingerprint",
            tier="scrapling-static",
            status=CheckStatus.ERROR,
            bar="informational",
            detail=f"{type(exc).__name__}: {exc}",
        )


async def _run_proxy_leak(proxy: str | None) -> CheckResult:
    """S4 — record the exit IP seen by an echo endpoint (proves egress path)."""
    try:
        page = await AsyncFetcher.get(
            "https://api.ipify.org?format=json",
            impersonate="chrome",
            proxy=proxy,
            timeout=30,
        )
        data = page.json()
        ip = data.get("ip") if isinstance(data, dict) else None
        note = "via proxy" if proxy else "DIRECT (no proxy — datacenter IP)"
        return CheckResult(
            suite="S",
            name="exit_ip",
            tier="scrapling-static",
            status=CheckStatus.INFO,
            bar="not your real/datacenter IP",
            detail=f"exit_ip={ip} ({note})",
        )
    except Exception as exc:
        return CheckResult(
            suite="S",
            name="exit_ip",
            tier="scrapling-static",
            status=CheckStatus.ERROR,
            bar="n/a",
            detail=f"{type(exc).__name__}: {exc}",
        )


async def run_suite_s(
    *, proxy: str | None, headed: bool, screenshots: bool
) -> list[CheckResult]:
    """Run the full stealth suite (browser tier sites + TLS + proxy + manual links)."""
    results: list[CheckResult] = []

    # Browser sites are sync (spin up a real browser) → offload per-site so one
    # slow score doesn't stall the loop and the event loop stays clean.
    for site in _BROWSER_SITES:
        print(f"  [S] {site.name} ... (settle {site.settle_ms}ms)")
        res = await asyncio.to_thread(
            _run_browser_site,
            site,
            proxy=proxy,
            headed=headed,
            screenshots=screenshots,
        )
        results.append(res)

    print("  [S] tls_fingerprint + exit_ip ...")
    results.append(await _run_tls(proxy))
    results.append(await _run_proxy_leak(proxy))

    for name, url in _MANUAL_LINKS:
        results.append(
            CheckResult(
                suite="S",
                name=name,
                tier="manual",
                status=CheckStatus.INFO,
                bar="open in a real headed run + compare",
                detail=url,
            )
        )

    return results
