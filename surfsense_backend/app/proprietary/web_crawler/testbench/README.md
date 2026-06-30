# Crawler testbench — manual undetectability & extraction scorecard (Phase 3f)

A **manual, repeatable scorecard** for the Universal WebURL Crawler. It answers
one question with evidence: *how undetectable (and how correct) is the crawler
right now?* — so we know when the free-stack ceiling (`03e`) is reached and the
deferred paid-unblocker tier is worth flipping.

This is **dev/operator tooling**, not a product code path and **not** part of the
pytest suite (it hits the live internet and needs proxy creds). See
`plans/backend/03f-undetectability-testing.md` for the full design.

## What it measures (two axes, two suites)

- **Suite S — stealth / anti-bot:** drives the real `StealthyFetcher` tier
  (built from the **same** `app/proprietary/web_crawler/stealth.py` builder the
  crawler ships, so no test-vs-prod drift) against the standard bot-detection
  sites — sannysoft, deviceandbrowserinfo, reCAPTCHA v3, CreepJS, BrowserScan,
  incolumitas, fingerprint-scan, FingerprintJS Pro, a **Cloudflare-challenge
  canary** (the only row that exercises `solve_cloudflare`), and iphey — plus the
  HTTP-tier TLS fingerprint (`tls.peet.ws`), exit-IP echo, and manual
  per-property links (browserleaks). Every detection site is **auto-graded** from
  its real DOM verdict (no screenshot reading required).
- **Suite E — extraction correctness:** drives the real `crawl_url` ladder
  against ToS-safe scraping sandboxes (`toscrape`, `scrapethissite`) and asserts
  known content appears in the extracted markdown.

## Run it

From the backend directory (`surfsense_backend/`):

```bash
uv run python -m app.proprietary.web_crawler.testbench --suite all
# or
.\.venv\Scripts\python.exe -m app.proprietary.web_crawler.testbench --suite all
```

Flags:

| Flag | Meaning |
|---|---|
| `--suite S\|E\|all` | Which suite(s) to run (default `all`). |
| `--proxy URL` | Override the proxy for Suite S (default: the app proxy provider from `.env`). |
| `--headed` | Run the browser tier headful (`headless=False`). |
| `--no-screenshots` | Skip per-site screenshots. |

Captcha solving is **forced OFF** every run — Suite S measures the *unaided*
stealth score.

## Reading the output

Each row prints `PASS / FAIL / ERR / INFO` with the tier and (where one exists) a
numeric. The harness is **tolerant**: a parse miss is `ERROR`, never a crash.
Detection sites are auto-graded from their DOM verdict; `INFO` is reserved for
purely informational rows (TLS fingerprint, exit IP) and the manual
per-property links (browserleaks canvas/webgl/fonts/webrtc). Screenshots are
still captured for every browser row as a backstop.

Outputs land in `results/`, which is **entirely gitignored** (run-local):

- `scorecard-<ts>.json` / `.md` — timestamped scorecard + readable report.
- `latest.json` — convenience pointer.
- `screenshots/` — per-site full-page captures.

Every run prints **drift vs the last baseline** (the previous on-disk scorecard)
so you can see the trend (our stealth improving, or a WAF tightening).

## The aspirational bars (from CloakBrowser, recorded as targets)

`sannysoft` 0 failed cells · `deviceandbrowserinfo` isBot=false ·
reCAPTCHA v3 `>= 0.7` · CreepJS headless `<= 30%`, no spoof tells · FingerprintJS
demo not blocked · Cloudflare challenge bypassed · iphey `Trustworthy`. We
**record our actual numbers as the baseline** — these are targets, not build
gates (the run never blocks anything).

## Caveats

- **Proxy required for realism.** Without residential egress the hard rows fail
  by design (datacenter IP); a red scorecard from no-proxy is expected.
- **Sites change.** Detection sites move their DOM; if an auto-parser starts
  returning `INFO`/`ERROR`, read the screenshot and (optionally) tighten the
  parser — each site is one entry in `suite_stealth.py`.
- **Not a guarantee.** Passing sannysoft/CreepJS ≠ beating DataDome/Kasada; the
  value is *trend + ceiling visibility*, not a green checkmark.
