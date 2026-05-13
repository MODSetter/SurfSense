"""Download CRAG Task 3's 4 .tar.bz2 parts in parallel.

Run once before ``ingest research crag_t3`` to avoid the ingest
synchronously blocking on a 7 GB download. Skips parts already
present and complete on disk.
"""

from __future__ import annotations

import logging
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("download_task3")


_BASE = (
    "https://github.com/facebookresearch/CRAG/raw/refs/heads/main/data/"
    "crag_task_3_dev_v4.tar.bz2.part"
)
_USER_AGENT = "SurfSense-Evals/0.1 (CRAG Task 3 fetch)"


def _expected_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return int(resp.headers.get("content-length", 0))


def download_one(part: int, dest_dir: Path) -> Path:
    url = f"{_BASE}{part}"
    dest = dest_dir / f"crag_task_3_dev_v4.tar.bz2.part{part}"
    expected = _expected_size(url)
    if dest.exists() and dest.stat().st_size == expected:
        log.info("part%d: cached (%d bytes)", part, expected)
        return dest
    log.info("part%d: downloading %d bytes ...", part, expected)
    tmp = dest.with_suffix(dest.suffix + ".part_dl")
    started = time.monotonic()
    last_log = started
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}),
        timeout=900,
    ) as resp, tmp.open("wb") as fh:
        downloaded = 0
        chunk = resp.read(1 << 20)
        while chunk:
            fh.write(chunk)
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_log > 5.0:
                pct = 100 * downloaded / expected if expected else 0
                rate_mb = (downloaded / (now - started)) / (1 << 20)
                log.info(
                    "part%d: %5.1f%% (%.1f / %.1f MiB at %.1f MiB/s)",
                    part, pct, downloaded / (1 << 20), expected / (1 << 20), rate_mb,
                )
                last_log = now
            chunk = resp.read(1 << 20)
    tmp.replace(dest)
    elapsed = time.monotonic() - started
    log.info(
        "part%d: done in %.1fs (%.1f MiB/s avg)",
        part, elapsed, (expected / (1 << 20)) / max(elapsed, 0.001),
    )
    return dest


def main() -> int:
    dest_dir = Path("data/research/crag_t3/.raw_cache")
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 4 parts in parallel — typical residential connection saturates around
    # 2 streams; GitHub raw serves these fine in parallel.
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(download_one, i, dest_dir): i for i in range(1, 5)}
        for fut in as_completed(futures):
            part = futures[fut]
            try:
                fut.result()
            except Exception as exc:  # noqa: BLE001
                log.error("part%d failed: %s", part, exc)
                return 1
    log.info("All 4 parts downloaded in %.1fs", time.monotonic() - started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
