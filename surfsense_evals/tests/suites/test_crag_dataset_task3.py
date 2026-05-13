"""Unit tests for CRAG Task 3 streaming dataset loader.

We don't (and shouldn't) hit the real 7 GB upstream archive in
unit tests. Instead we construct tiny tar.bz2 archives split across
N parts and verify:

* ``_MultiPartReader`` correctly stitches N files together.
* The streaming path (multi → bz2 → tar → JSONL) yields parsed
  ``CragQuestion`` rows with the right shape.
* ``max_questions`` cap is honoured (early break, no greedy read).
* ``parts_present`` correctly detects missing/empty parts.
"""

from __future__ import annotations

import bz2
import io
import json
import tarfile
from pathlib import Path

import pytest

from surfsense_evals.suites.research.crag.dataset_task3 import (
    _MultiPartReader,
    iter_questions_task3,
    parts_present,
)


# ---------------------------------------------------------------------------
# Fixtures: build a tiny synthetic Task 3 archive
# ---------------------------------------------------------------------------


def _make_jsonl_payload(n_rows: int) -> bytes:
    rows = []
    for i in range(n_rows):
        rows.append({
            "interaction_id": f"int_{i:04d}",
            "query_time": "2024-01-01 00:00:00",
            "domain": ["finance", "music", "movie", "sports", "open"][i % 5],
            "question_type": ["simple", "comparison", "aggregation", "multi-hop"][i % 4],
            "static_or_dynamic": "static",
            "popularity": "head",
            "split": 0,
            "query": f"Synthetic CRAG question {i}?",
            "answer": f"answer-{i}",
            "alt_ans": [f"alt-{i}-a", f"alt-{i}-b"],
            "search_results": [
                {
                    "page_name": f"Page {j} for q{i}",
                    "page_url": f"https://example.com/q{i}/p{j}",
                    "page_snippet": "snippet",
                    "page_result": f"<html><body><p>q{i} p{j} body</p></body></html>",
                    "page_last_modified": "",
                }
                for j in range(50)
            ],
        })
    return b"\n".join(json.dumps(r).encode("utf-8") for r in rows) + b"\n"


def _make_tar_bz2(jsonl_bytes: bytes, *, member_name: str = "data.jsonl") -> bytes:
    bio = io.BytesIO()
    with bz2.BZ2File(bio, mode="wb") as bz:
        with tarfile.open(fileobj=bz, mode="w") as tar:
            info = tarfile.TarInfo(name=member_name)
            info.size = len(jsonl_bytes)
            tar.addfile(info, io.BytesIO(jsonl_bytes))
    return bio.getvalue()


def _make_tar_bz2_multi(shards: list[tuple[str, bytes]]) -> bytes:
    """Build a tar.bz2 archive containing multiple JSONL shards.

    Mirrors the real CRAG Task 3 layout: one tar with N JSONL members
    named ``crag_task_3_dev_v4_{i}.jsonl`` (or whatever the caller
    passes in).
    """

    bio = io.BytesIO()
    with bz2.BZ2File(bio, mode="wb") as bz:
        with tarfile.open(fileobj=bz, mode="w") as tar:
            for name, payload in shards:
                info = tarfile.TarInfo(name=name)
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
    return bio.getvalue()


def _split_into_parts(blob: bytes, n_parts: int) -> list[bytes]:
    """Split byte string into N roughly-equal chunks (last gets remainder)."""
    chunk = max(1, len(blob) // n_parts)
    parts = [blob[i * chunk : (i + 1) * chunk] for i in range(n_parts - 1)]
    parts.append(blob[(n_parts - 1) * chunk :])
    return parts


@pytest.fixture
def task3_parts_dir(tmp_path: Path) -> Path:
    """A directory containing a 4-part synthetic CRAG Task 3 archive (12 rows)."""
    blob = _make_tar_bz2(_make_jsonl_payload(12))
    parts = _split_into_parts(blob, 4)
    parts_dir = tmp_path / ".raw_cache"
    parts_dir.mkdir()
    for i, b in enumerate(parts, start=1):
        (parts_dir / f"crag_task_3_dev_v4.tar.bz2.part{i}").write_bytes(b)
    return parts_dir


# ---------------------------------------------------------------------------
# _MultiPartReader
# ---------------------------------------------------------------------------


class TestMultiPartReader:
    def test_concatenates_parts_in_order(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        c = tmp_path / "c"
        a.write_bytes(b"hello, ")
        b.write_bytes(b"streaming ")
        c.write_bytes(b"world!")
        with _MultiPartReader([a, b, c]) as r:
            assert r.read() == b"hello, streaming world!"

    def test_read_n_crosses_part_boundary(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"AAA")
        b.write_bytes(b"BBBB")
        with _MultiPartReader([a, b]) as r:
            # Read 5 bytes — straddles boundary between parts.
            assert r.read(5) == b"AAABB"
            assert r.read(5) == b"BB"
            assert r.read(5) == b""

    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.write_bytes(b"x")
        r = _MultiPartReader([a])
        r.close()
        r.close()
        with pytest.raises(ValueError):
            r.read(1)

    def test_missing_part_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            _MultiPartReader([tmp_path / "does-not-exist"])

    def test_empty_paths_raises(self) -> None:
        with pytest.raises(ValueError):
            _MultiPartReader([])


# ---------------------------------------------------------------------------
# iter_questions_task3
# ---------------------------------------------------------------------------


@pytest.fixture
def task3_multi_shard_dir(tmp_path: Path) -> Path:
    """A 4-part archive whose tar contains 3 JSONL shards (4 + 4 + 4 rows)."""
    payload_a = _make_jsonl_payload(4)
    payload_b = _make_jsonl_payload(4)
    payload_c = _make_jsonl_payload(4)
    blob = _make_tar_bz2_multi([
        ("crag_task_3_dev_v4_0.jsonl", payload_a),
        ("crag_task_3_dev_v4_1.jsonl", payload_b),
        ("crag_task_3_dev_v4_2.jsonl", payload_c),
    ])
    parts = _split_into_parts(blob, 4)
    parts_dir = tmp_path / ".raw_cache"
    parts_dir.mkdir()
    for i, b in enumerate(parts, start=1):
        (parts_dir / f"crag_task_3_dev_v4.tar.bz2.part{i}").write_bytes(b)
    return parts_dir


class TestIterQuestionsTask3:
    def test_streams_full_archive(self, task3_parts_dir: Path) -> None:
        questions = iter_questions_task3(task3_parts_dir)
        assert len(questions) == 12
        # All questions get the T3_ prefix and 50 pages each.
        assert all(q.qid.startswith("T3_") for q in questions)
        assert all(len(q.pages) == 50 for q in questions)
        # Schema fields preserved.
        first = questions[0]
        assert first.query == "Synthetic CRAG question 0?"
        assert first.gold_answer == "answer-0"
        assert first.domain == "finance"
        assert "alt-0-a" in first.alt_answers

    def test_max_questions_caps_early(self, task3_parts_dir: Path) -> None:
        questions = iter_questions_task3(task3_parts_dir, max_questions=3)
        assert len(questions) == 3
        # Sequential indices 0..2 — we don't skip rows.
        assert [q.raw_index for q in questions] == [0, 1, 2]

    def test_streams_multi_shard_archive(self, task3_multi_shard_dir: Path) -> None:
        # Three shards × four rows each = twelve rows total.
        questions = iter_questions_task3(task3_multi_shard_dir)
        assert len(questions) == 12
        # raw_index increments monotonically across shards.
        assert [q.raw_index for q in questions] == list(range(12))
        # qids are unique and sequential across shards.
        assert len({q.qid for q in questions}) == 12

    def test_max_questions_short_circuits_first_shard(self, task3_multi_shard_dir: Path) -> None:
        # Cap < shard size — shouldn't touch shards 1 or 2 at all.
        questions = iter_questions_task3(task3_multi_shard_dir, max_questions=2)
        assert len(questions) == 2
        # Both come from shard 0 (raw_index 0, 1).
        assert [q.raw_index for q in questions] == [0, 1]

    def test_max_questions_spans_shards(self, task3_multi_shard_dir: Path) -> None:
        # Cap = 6 → all 4 from shard 0 + first 2 from shard 1.
        questions = iter_questions_task3(task3_multi_shard_dir, max_questions=6)
        assert len(questions) == 6
        assert [q.raw_index for q in questions] == [0, 1, 2, 3, 4, 5]

    def test_raises_when_no_jsonl_member(self, tmp_path: Path) -> None:
        # Archive containing a non-jsonl member.
        bio = io.BytesIO()
        with bz2.BZ2File(bio, mode="wb") as bz:
            with tarfile.open(fileobj=bz, mode="w") as tar:
                info = tarfile.TarInfo(name="README.md")
                payload = b"not jsonl"
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
        parts_dir = tmp_path / ".raw_cache"
        parts_dir.mkdir()
        for i, name in enumerate(
            ("part1", "part2", "part3", "part4"), start=1,
        ):
            half = len(bio.getvalue()) // 4
            chunk = bio.getvalue()[(i - 1) * half : i * half if i < 4 else len(bio.getvalue())]
            (parts_dir / f"crag_task_3_dev_v4.tar.bz2.{name}").write_bytes(chunk)
        with pytest.raises(RuntimeError, match="No JSONL member"):
            iter_questions_task3(parts_dir)


# ---------------------------------------------------------------------------
# parts_present
# ---------------------------------------------------------------------------


class TestPartsPresent:
    def test_all_present(self, task3_parts_dir: Path) -> None:
        assert parts_present(task3_parts_dir) is True

    def test_one_missing(self, task3_parts_dir: Path) -> None:
        (task3_parts_dir / "crag_task_3_dev_v4.tar.bz2.part2").unlink()
        assert parts_present(task3_parts_dir) is False

    def test_one_empty(self, task3_parts_dir: Path) -> None:
        (task3_parts_dir / "crag_task_3_dev_v4.tar.bz2.part3").write_bytes(b"")
        assert parts_present(task3_parts_dir) is False
