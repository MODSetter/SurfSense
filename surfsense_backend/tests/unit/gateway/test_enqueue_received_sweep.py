from __future__ import annotations

from app.tasks.celery_tasks import gateway_tasks


def test_enqueue_received_sweep_is_noop_guard(mocker):
    apply_async = mocker.Mock()
    mocker.patch.object(gateway_tasks.process_inbound_event_task, "apply_async", apply_async)
    info = mocker.patch.object(gateway_tasks.logger, "info")

    replayed = gateway_tasks.enqueue_received_sweep_task.run()

    apply_async.assert_not_called()
    assert replayed == 0
    info.assert_called_once()

