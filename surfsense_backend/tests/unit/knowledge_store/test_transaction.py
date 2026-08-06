"""Transaction: staged verbs resolve into one net change set (pure logic)."""

from __future__ import annotations

import pytest

from app.knowledge_store.transaction import Transaction

pytestmark = pytest.mark.unit


def _no_committed_content(_path: str) -> bytes | None:
    return None


class TestResolve:
    def test_writes_and_removes_pass_through(self):
        tx = Transaction()
        tx.write("a.xml", b"a")
        tx.remove("b.xml")

        writes, removes = tx.resolve(_no_committed_content)
        assert writes == {"a.xml": b"a"}
        assert removes == ["b.xml"]

    def test_write_after_remove_nets_to_a_write(self):
        tx = Transaction()
        tx.remove("a.xml")
        tx.write("a.xml", b"new")

        writes, removes = tx.resolve(_no_committed_content)
        assert writes == {"a.xml": b"new"}
        assert removes == []

    def test_remove_after_write_nets_to_a_remove(self):
        tx = Transaction()
        tx.write("a.xml", b"x")
        tx.remove("a.xml")

        writes, removes = tx.resolve(_no_committed_content)
        assert writes == {}
        assert removes == ["a.xml"]

    def test_move_of_content_written_in_the_same_transaction(self):
        tx = Transaction()
        tx.write("old.xml", b"content")
        tx.move("old.xml", "new.xml")

        writes, removes = tx.resolve(_no_committed_content)
        assert writes == {"new.xml": b"content"}
        assert removes == ["old.xml"]

    def test_move_of_committed_content_reads_it_from_the_store(self):
        tx = Transaction()
        tx.move("old.xml", "new.xml")

        writes, removes = tx.resolve(
            lambda path: b"committed" if path == "old.xml" else None
        )
        assert writes == {"new.xml": b"committed"}
        assert removes == ["old.xml"]

    def test_move_of_a_missing_path_raises(self):
        tx = Transaction()
        tx.move("ghost.xml", "new.xml")

        with pytest.raises(FileNotFoundError):
            tx.resolve(_no_committed_content)
