"""An idle worker that holds its models' memory leaves for a fresh one."""

import signal
import threading
from typing import Any

import pytest

from worker import consumer
from worker.fresh_start import (
    FRESH_START_EXIT_CODE,
    IdleWatch,
    watch_for_fresh_start,
)

pytestmark = pytest.mark.unit

MB = 1024 * 1024


class _Queue:
    """Huey's hook registration, holding the hooks for the test to call."""

    def __init__(self) -> None:
        self.before: Any = None
        self.after: Any = None

    def pre_execute(self, name: str) -> Any:
        def register(hook: Any) -> Any:
            self.before = hook
            return hook

        return register

    def post_execute(self, name: str) -> Any:
        def register(hook: Any) -> Any:
            self.after = hook
            return hook

        return register


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def watched() -> tuple[_Queue, _Clock, IdleWatch]:
    """A watch on a stand-in queue, with a clock the test moves."""
    queue, clock = _Queue(), _Clock()
    return queue, clock, IdleWatch(queue, idle_seconds=300, held=400 * MB, clock=clock)


def test_a_worker_that_has_done_nothing_never_leaves(watched: Any) -> None:
    """A new worker holds little, so it cannot restart in a loop."""
    _queue, clock, watch = watched
    clock.now += 3600

    assert not watch.due(2000 * MB)


def test_it_leaves_once_idle_long_enough_after_work_holding_much(watched: Any) -> None:
    """Five idle minutes after its last task, as sd-server and audio.cpp unload."""
    queue, clock, watch = watched
    queue.before("ingest_document")
    queue.after("ingest_document", None, None)

    clock.now += 299
    assert not watch.due(2000 * MB)
    clock.now += 1
    assert watch.due(2000 * MB)


def test_it_stays_while_a_task_runs_however_long(watched: Any) -> None:
    """Studio runs four at once: one still running keeps the worker."""
    queue, clock, watch = watched
    queue.before("studio_job")
    queue.after("studio_job", None, None)
    queue.before("studio_job")
    clock.now += 3600

    assert not watch.due(2000 * MB)


def test_it_stays_when_it_holds_little(watched: Any) -> None:
    """An embedder alone is cheaper to keep than to load again."""
    queue, clock, watch = watched
    queue.before("ingest_document")
    queue.after("ingest_document", None, ValueError("failed"))
    clock.now += 3600

    assert not watch.due(250 * MB)
    assert watch.due(400 * MB)


def test_the_ask_is_huey_s_own_graceful_stop(watched: Any) -> None:
    """SIGINT makes the running consumer finish each thread's task before it returns."""
    queue, clock, watch = watched
    queue.before("ingest_document")
    queue.after("ingest_document", None, None)
    clock.now += 600
    received = threading.Event()
    previous = signal.signal(signal.SIGINT, lambda *_: received.set())
    try:
        asked = watch_for_fresh_start(watch, every=0.01, measure=lambda: 2000 * MB)
        for _ in range(500):
            if received.is_set():
                break
            threading.Event().wait(0.01)
    finally:
        signal.signal(signal.SIGINT, previous)

    assert asked.is_set()
    assert received.is_set()


def test_a_consumer_stopped_for_a_fresh_start_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any other code reads as a crash to the supervisor, which then starts none."""

    class FakeConsumer:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def run(self) -> None:
            pass

    asked = threading.Event()
    asked.set()
    monkeypatch.setattr(consumer, "Consumer", FakeConsumer)
    monkeypatch.setattr(consumer, "watch_for_fresh_start", lambda _watch: asked)
    monkeypatch.setattr(consumer, "wait_for_schema", lambda: None)
    monkeypatch.setattr(consumer, "fail_interrupted_documents", lambda _kinds: None)

    with pytest.raises(SystemExit) as exited:
        consumer.consume("ingest")

    assert exited.value.code == FRESH_START_EXIT_CODE == 75
