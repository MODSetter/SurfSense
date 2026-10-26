"""The on-device counts: hourly, pruned, never content, and honest about when they began."""

from datetime import UTC, datetime, timedelta

import pytest

from modules.usage_statistics.activity_counts import (
    Activity,
    count_agent_turn,
    count_chat_answer,
    count_plugin_calls,
    read_counts,
)
from modules.usage_statistics.activity_counts.counts_file import (
    add,
    counts_path,
    start_counting,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 21, 12, 30, tzinfo=UTC)


def test_nothing_is_known_before_the_file_exists() -> None:
    """No file, no counts: the summary then says unknown."""
    assert read_counts() is None


def test_a_library_with_no_chats_misses_nothing_when_counting_starts() -> None:
    """A new install's counts cover every window, however early it starts."""
    start_counting(had_chats=False, now=NOW)

    counts = read_counts()
    assert counts is not None
    assert counts.covers(NOW - timedelta(days=365))


def test_a_library_with_chats_is_counted_only_from_now() -> None:
    """Turns before the update were never counted, so a window reaching back is not covered."""
    start_counting(had_chats=True, now=NOW)

    counts = read_counts()
    assert counts is not None
    assert not counts.covers(NOW - timedelta(days=7))
    assert counts.covers(NOW + timedelta(minutes=1))


def test_starting_again_keeps_the_counts_already_there() -> None:
    """Every start calls it; only the first may set when counting began."""
    start_counting(had_chats=False, now=NOW)
    add({Activity.AGENT_TURN: 1}, now=NOW)

    start_counting(had_chats=True, now=NOW + timedelta(days=1))

    counts = read_counts()
    assert counts is not None
    assert counts.counted_since is None
    assert counts.total(Activity.AGENT_TURN, NOW - timedelta(hours=1)) == 1


def test_a_window_counts_only_the_hours_inside_it() -> None:
    """Keyed by the hour, so a seven-day window is right to the hour."""
    start_counting(had_chats=False, now=NOW)
    add({Activity.PLUGIN_CALL: 2}, now=NOW - timedelta(days=8))
    add({Activity.PLUGIN_CALL: 3}, now=NOW - timedelta(days=2))
    add({Activity.PLUGIN_CALL: 1}, now=NOW)

    counts = read_counts()
    assert counts is not None
    assert counts.total(Activity.PLUGIN_CALL, NOW - timedelta(days=7)) == 4


def test_hours_older_than_forty_days_are_dropped() -> None:
    """Nothing the weekly report could ask for is kept longer than it needs,
    but that a model once answered outlives the hour it answered in."""
    add({Activity.LOCAL_ANSWER: 1}, now=NOW - timedelta(days=41))
    add({Activity.AGENT_TURN: 1}, now=NOW)

    counts = read_counts()
    assert counts is not None
    assert len(counts.hours) == 1
    assert counts.answered


async def test_an_agent_turn_alone_is_not_an_answer() -> None:
    """A turn sent may still fail; only a reply with text marks an answer."""
    await count_agent_turn()

    counts = read_counts()
    assert counts is not None
    assert (
        counts.total(Activity.AGENT_TURN, datetime.now(UTC) - timedelta(hours=1)) == 1
    )
    assert not counts.answered


def test_a_missing_file_starts_from_the_first_count() -> None:
    """Counts begun without a start only vouch for the time after them."""
    add({Activity.LOCAL_ANSWER: 1}, now=NOW)

    counts = read_counts()
    assert counts is not None
    assert counts.counted_since == NOW


def test_an_unreadable_file_is_no_counts_and_is_replaced_by_the_next() -> None:
    """A broken file never fails a turn; it is started over and says so."""
    counts_path().write_text("{not json")
    assert read_counts() is None

    add({Activity.REMOTE_ANSWER: 1}, now=NOW)

    counts = read_counts()
    assert counts is not None
    assert counts.counted_since == NOW


async def test_a_chat_answer_is_counted_by_the_kind_of_model() -> None:
    """SurfSense's own llama.cpp is local; any connection is remote."""
    await count_chat_answer("llamacpp")
    await count_chat_answer("openai_compatible")

    counts = read_counts()
    assert counts is not None
    since = datetime.now(UTC) - timedelta(hours=1)
    assert counts.total(Activity.LOCAL_ANSWER, since) == 1
    assert counts.total(Activity.REMOTE_ANSWER, since) == 1


async def test_plugin_calls_count_each_tool_call_and_nothing_else() -> None:
    """A batch carries several; listing tools or a malformed body counts none."""
    await count_plugin_calls(
        b'[{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"a"}},'
        b'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"b"}}]'
    )
    await count_plugin_calls(b'{"jsonrpc":"2.0","id":3,"method":"tools/list"}')
    await count_plugin_calls(b"not json")

    counts = read_counts()
    assert counts is not None
    since = datetime.now(UTC) - timedelta(hours=1)
    assert counts.total(Activity.PLUGIN_CALL, since) == 2


def test_the_file_holds_counts_and_nothing_that_says_what_was_asked() -> None:
    """Only activity names, hours and numbers are written."""
    add({Activity.AGENT_TURN: 1, Activity.PLUGIN_CALL: 2}, now=NOW)

    text = counts_path().read_text()
    assert set(read_counts().hours["2026-10-21T12"]) == {"agent_turns", "plugin_calls"}
    assert "tools/call" not in text
