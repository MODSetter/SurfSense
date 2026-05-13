"""CRAG Task 3 dataset loader — 4-part tar.bz2 → streaming JSONL.

Task 3 ships ~7 GB of compressed data split into 4 parts on GitHub:

    crag_task_3_dev_v4.tar.bz2.part1    (≈2 GB)
    crag_task_3_dev_v4.tar.bz2.part2    (≈2 GB)
    crag_task_3_dev_v4.tar.bz2.part3    (≈2 GB)
    crag_task_3_dev_v4.tar.bz2.part4    (≈1.3 GB)

Concatenated, they form a tar archive containing a single JSONL file.
Decompressed, that JSONL is on the order of 30-50 GB because each row
embeds 50 full HTML pages (vs 5 in Tasks 1 & 2).

Materialising the JSONL would blow the disk budget (we have ~50 GB
free at the time of writing), so we stream the whole thing instead:

  1. Download parts (idempotent; ``scripts/download_crag_task3.py``).
  2. Concat them into a virtual file via ``_MultiPartReader``.
  3. Wrap in ``bz2.BZ2File`` for on-the-fly decompression.
  4. Wrap in ``tarfile.open(fileobj=..., mode="r|")`` for streaming
     tar member iteration.
  5. For the JSONL member inside, ``tar.extractfile()`` returns a
     binary file-like; we iterate lines and yield parsed dicts.

The caller can ``break`` out as soon as they have enough samples —
nothing past the consumed point is decompressed.

Schema is identical to Tasks 1 & 2 (see ``dataset.py``); only
``search_results`` is bigger (50 entries instead of 5).
"""

from __future__ import annotations

import bz2
import json
import logging
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from .dataset import (
    CragPage,
    CragQuestion,
    _parse_alt_answers,
    _parse_pages,
)

logger = logging.getLogger(__name__)


CRAG_TASK_3_PART_URLS: tuple[str, ...] = tuple(
    "https://github.com/facebookresearch/CRAG/raw/refs/heads/main/data/"
    f"crag_task_3_dev_v4.tar.bz2.part{i}"
    for i in (1, 2, 3, 4)
)
CRAG_TASK_3_PART_NAMES: tuple[str, ...] = tuple(
    f"crag_task_3_dev_v4.tar.bz2.part{i}" for i in (1, 2, 3, 4)
)


# ---------------------------------------------------------------------------
# Multi-part virtual file (concatenates N files transparently)
# ---------------------------------------------------------------------------


class _MultiPartReader:
    """Read N files end-to-end as if they were one big file.

    Implements just enough of the file protocol for ``bz2.BZ2File``
    to consume it: ``read(n)``, ``readable()``, ``close()``.
    Doesn't implement ``seek`` — the bz2 + tarfile streaming path
    is forward-only, which is what we want here.
    """

    def __init__(self, paths: list[Path]) -> None:
        if not paths:
            raise ValueError("_MultiPartReader needs at least one path")
        for p in paths:
            if not p.exists():
                raise FileNotFoundError(p)
        self._paths = list(paths)
        self._idx = 0
        self._fh: IO[bytes] | None = self._paths[0].open("rb")
        self._closed = False

    def read(self, n: int = -1) -> bytes:
        if self._closed:
            raise ValueError("read of closed _MultiPartReader")
        if n is None or n < 0:
            chunks: list[bytes] = []
            while self._fh is not None:
                chunks.append(self._fh.read())
                self._advance()
            return b"".join(chunks)
        out: list[bytes] = []
        remaining = n
        while remaining > 0 and self._fh is not None:
            chunk = self._fh.read(remaining)
            if not chunk:
                self._advance()
                continue
            out.append(chunk)
            remaining -= len(chunk)
        return b"".join(out)

    def _advance(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self._idx += 1
        if self._idx < len(self._paths):
            self._fh = self._paths[self._idx].open("rb")

    def readable(self) -> bool:
        return not self._closed

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self._closed = True

    def __enter__(self) -> _MultiPartReader:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.close()


# ---------------------------------------------------------------------------
# Stream the JSONL inside the tar.bz2
# ---------------------------------------------------------------------------


def _is_jsonl_member(name: str) -> bool:
    return name.endswith(".jsonl") or name.endswith(".jsonl.txt")


def iter_questions_task3(
    parts_dir: Path,
    *,
    max_questions: int | None = None,
) -> list[CragQuestion]:
    """Stream-parse Task 3 rows into ``CragQuestion`` objects.

    The Task 3 archive ships its 2,706 questions sharded across
    multiple JSONL files inside the tar (e.g.
    ``crag_task_3_dev_v4_0.jsonl``, ``..._1.jsonl``, …). We iterate
    members in-stream, parse every JSONL one we encounter, and stop
    as soon as ``max_questions`` is reached — at which point we
    don't decompress any further members.

    For a typical n=50 sample at ~3 MB per row we touch ~150 MB of
    decompressed JSONL — almost always inside the first shard.
    """

    parts = [parts_dir / name for name in CRAG_TASK_3_PART_NAMES]
    multi = _MultiPartReader(parts)
    bz = bz2.BZ2File(multi, mode="rb")
    tar = tarfile.open(fileobj=bz, mode="r|")
    out: list[CragQuestion] = []
    raw_idx = 0
    found_jsonl = False
    try:
        for member in tar:
            if not member.isfile() or not _is_jsonl_member(member.name):
                continue
            found_jsonl = True
            logger.info(
                "CRAG Task 3: streaming JSONL shard %s (size: %d bytes)",
                member.name, member.size,
            )
            fh = tar.extractfile(member)
            if fh is None:
                logger.warning("tar.extractfile returned None for %s; skipping", member.name)
                continue
            try:
                for raw_line in fh:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.warning(
                            "Skipping malformed CRAG Task 3 row %d in %s: %s",
                            raw_idx, member.name, exc,
                        )
                        raw_idx += 1
                        continue
                    query = str(row.get("query") or "").strip()
                    answer = str(row.get("answer") or "").strip()
                    if not query or not answer:
                        raw_idx += 1
                        continue
                    out.append(CragQuestion(
                        qid=f"T3_{raw_idx:05d}",
                        interaction_id=str(row.get("interaction_id") or "").strip(),
                        query_time=str(row.get("query_time") or "").strip(),
                        query=query,
                        gold_answer=answer,
                        alt_answers=_parse_alt_answers(row.get("alt_ans")),
                        domain=str(row.get("domain") or "").strip().lower(),
                        question_type=str(row.get("question_type") or "").strip().lower(),
                        static_or_dynamic=str(row.get("static_or_dynamic") or "").strip().lower(),
                        popularity=str(row.get("popularity") or "").strip().lower(),
                        split=int(row.get("split") or 0),
                        raw_index=raw_idx,
                        pages=_parse_pages(row.get("search_results")),
                    ))
                    raw_idx += 1
                    if max_questions is not None and len(out) >= max_questions:
                        return out
            finally:
                try:
                    fh.close()
                except Exception:  # noqa: BLE001
                    pass
        if not found_jsonl:
            raise RuntimeError(
                "No JSONL member found inside Task 3 tar.bz2 archive; "
                "schema may have changed upstream."
            )
    finally:
        try:
            tar.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            bz.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            multi.close()
        except Exception:  # noqa: BLE001
            pass
    return out


def parts_present(parts_dir: Path) -> bool:
    """``True`` iff all 4 parts exist on disk and are non-empty."""

    for name in CRAG_TASK_3_PART_NAMES:
        p = parts_dir / name
        if not p.exists() or p.stat().st_size == 0:
            return False
    return True


# ---------------------------------------------------------------------------
# Re-exports for convenience
# ---------------------------------------------------------------------------


__all__ = [
    "CRAG_TASK_3_PART_NAMES",
    "CRAG_TASK_3_PART_URLS",
    "CragPage",
    "CragQuestion",
    "iter_questions_task3",
    "parts_present",
]
