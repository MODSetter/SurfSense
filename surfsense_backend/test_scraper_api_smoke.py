"""One-shot smoke test: hit every scraper API endpoint with a PAT, print PASS/FAIL."""

import json
import os
import sys
import time

import httpx

BASE = "http://localhost:8000/api/v1/workspaces/12/scrapers"
PAT = os.environ["SURFSENSE_PAT"]  # export a ss_pat_... key before running
HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

# Minimal payloads: 1-3 items each to keep credit spend tiny.
VERBS = [
    ("google_search/scrape", {"queries": ["surfsense github"], "max_pages_per_query": 1}),
    ("web/crawl", {"startUrls": ["https://example.com"], "maxCrawlDepth": 0}),
    ("reddit/scrape", {"urls": ["https://www.reddit.com/r/Python/"], "max_items": 3}),
    ("youtube/scrape", {"search_queries": ["python tutorial"], "max_results": 1}),
    (
        "youtube/comments",
        {"urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"], "max_comments": 3},
    ),
    (
        "google_maps/scrape",
        {"search_queries": ["coffee shop"], "location": "New York, USA", "max_places": 1},
    ),
    (
        "google_maps/reviews",
        # Google Sydney office, a stable well-known place id.
        {"place_ids": ["ChIJN1t_tDeuEmsRUsoyG83frY4"], "max_reviews": 3},
    ),
]

results = []
client = httpx.Client(headers=HEADERS, timeout=300)
sync_run_id = None

for verb, payload in VERBS:
    t0 = time.time()
    try:
        r = client.post(f"{BASE}/{verb}", json=payload)
        dur = time.time() - t0
        run_id = r.headers.get("x-run-id")
        if r.status_code == 200:
            body = r.json()
            # Count items in whatever list field the output has.
            items = next((len(v) for v in body.values() if isinstance(v, list)), "?")
            results.append((verb, "PASS", f"{r.status_code} items={items} run={run_id} {dur:.1f}s"))
            if sync_run_id is None and run_id:
                sync_run_id = run_id
        else:
            results.append((verb, "FAIL", f"{r.status_code} {r.text[:200]} {dur:.1f}s"))
    except Exception as e:
        results.append((verb, "FAIL", f"{type(e).__name__}: {e}"))
    print(f"[{results[-1][1]}] {verb}: {results[-1][2]}", flush=True)

# --- Run history endpoints ---
r = client.get(f"{BASE}/runs", params={"limit": 5})
ok = r.status_code == 200 and isinstance(r.json(), list)
results.append(("GET runs (list)", "PASS" if ok else "FAIL", f"{r.status_code} rows={len(r.json()) if ok else '?'}"))
print(f"[{results[-1][1]}] GET runs: {results[-1][2]}", flush=True)

if sync_run_id:
    r = client.get(f"{BASE}/runs/{sync_run_id}")
    ok = r.status_code == 200 and r.json().get("id") == sync_run_id
    results.append(("GET runs/{id} (detail)", "PASS" if ok else "FAIL", f"{r.status_code} status={r.json().get('status') if ok else r.text[:100]}"))
    print(f"[{results[-1][1]}] GET run detail: {results[-1][2]}", flush=True)

# --- Async mode + SSE events ---
r = client.post(f"{BASE}/web/crawl?mode=async", json={"startUrls": ["https://example.com"]})
if r.status_code == 202:
    async_id = r.json()["run_id"]
    seen, finished = [], None
    with client.stream("GET", f"{BASE}/runs/{async_id}/events", timeout=120) as s:
        for line in s.iter_lines():
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                seen.append(ev["type"])
                if ev["type"] == "run.finished":
                    finished = ev.get("status")
                    break
    ok = finished == "success"
    results.append(("async + SSE events", "PASS" if ok else "FAIL", f"202 events={seen} final={finished}"))
else:
    results.append(("async + SSE events", "FAIL", f"{r.status_code} {r.text[:200]}"))
print(f"[{results[-1][1]}] async+SSE: {results[-1][2]}", flush=True)

# --- Cancel endpoint ---
r = client.post(f"{BASE}/web/crawl?mode=async", json={"startUrls": ["https://example.com"], "maxCrawlDepth": 2, "maxCrawlPages": 50})
if r.status_code == 202:
    cancel_id = r.json()["run_id"]
    time.sleep(1)
    r2 = client.post(f"{BASE}/runs/{cancel_id}/cancel")
    ok = r2.status_code == 200 and r2.json().get("status") == "cancelled"
    results.append(("POST runs/{id}/cancel", "PASS" if ok else "FAIL", f"{r2.status_code} {r2.text[:150]}"))
else:
    results.append(("POST runs/{id}/cancel", "FAIL", f"setup {r.status_code}"))
print(f"[{results[-1][1]}] cancel: {results[-1][2]}", flush=True)

print("\n===== SUMMARY =====")
for name, status_, detail in results:
    print(f"{status_:4} {name}: {detail}")
failed = [r for r in results if r[1] == "FAIL"]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
