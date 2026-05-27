from __future__ import annotations

from app.tasks.celery_tasks import gateway_tasks


def test_process_inbound_event_task_is_noop_guard(mocker):
    warning = mocker.patch.object(gateway_tasks.logger, "warning")

    assert gateway_tasks.process_inbound_event_task.run(123) is None

    warning.assert_called_once()
    assert "FastAPI owns external chat agent turn processing" in warning.call_args.args[0]

