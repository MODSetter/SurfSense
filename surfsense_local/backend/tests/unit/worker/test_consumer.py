import pytest

from modules.artifacts.tasks import studio_job
from modules.documents.tasks import ingest_document
from shared import queue
from worker import consumer

pytestmark = pytest.mark.unit


def test_each_task_is_enqueued_on_the_queue_its_consumer_drains() -> None:
    """Separate queues in one file: an import never queues ahead of a summary."""
    assert ingest_document.huey is queue.ingest_queue
    assert studio_job.huey is queue.studio_queue
    assert queue.ingest_queue.name != queue.studio_queue.name
    assert queue.ingest_queue.storage.filename == queue.studio_queue.storage.filename


def test_ingestion_runs_one_job_at_a_time_and_studio_several(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingestion saturates a CPU; Studio mostly waits on a model."""
    built: list[tuple[object, int]] = []

    class FakeConsumer:
        def __init__(self, huey: object, workers: int, **_: object) -> None:
            built.append((huey, workers))

        def run(self) -> None:
            pass

    monkeypatch.setattr(consumer, "Consumer", FakeConsumer)

    consumer.consume("ingest")
    consumer.consume("studio")

    assert built == [
        (queue.ingest_queue, 1),
        (queue.studio_queue, consumer.STUDIO_WORKERS),
    ]
    assert consumer.STUDIO_WORKERS > 1
    with pytest.raises(KeyError):
        consumer.consume("mail")
