"""Resume side-channel must be read exactly once per turn."""

from __future__ import annotations

from langchain.tools import ToolRuntime

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.config import (
    consume_surfsense_resume,
    has_surfsense_resume,
)


def _runtime_with_config(config: dict) -> ToolRuntime:
    return ToolRuntime(
        state=None,
        context=None,
        config=config,
        stream_writer=None,
        tool_call_id="tcid-test",
        store=None,
    )


class TestConsumeSurfsenseResume:
    def test_pops_value_on_first_call(self):
        runtime = _runtime_with_config(
            {"configurable": {"surfsense_resume_value": {"decisions": ["approve"]}}}
        )

        assert consume_surfsense_resume(runtime) == {"decisions": ["approve"]}

    def test_second_call_returns_none(self):
        configurable: dict = {"surfsense_resume_value": {"decisions": ["approve"]}}
        runtime = _runtime_with_config({"configurable": configurable})

        consume_surfsense_resume(runtime)

        assert consume_surfsense_resume(runtime) is None
        assert "surfsense_resume_value" not in configurable

    def test_returns_none_when_no_payload_queued(self):
        runtime = _runtime_with_config({"configurable": {}})

        assert consume_surfsense_resume(runtime) is None

    def test_returns_none_when_configurable_missing(self):
        runtime = _runtime_with_config({})

        assert consume_surfsense_resume(runtime) is None


class TestHasSurfsenseResume:
    def test_true_when_payload_queued(self):
        runtime = _runtime_with_config(
            {"configurable": {"surfsense_resume_value": "approve"}}
        )

        assert has_surfsense_resume(runtime) is True

    def test_does_not_consume_payload(self):
        configurable = {"surfsense_resume_value": "approve"}
        runtime = _runtime_with_config({"configurable": configurable})

        has_surfsense_resume(runtime)

        assert configurable == {"surfsense_resume_value": "approve"}

    def test_false_when_payload_absent(self):
        runtime = _runtime_with_config({"configurable": {}})

        assert has_surfsense_resume(runtime) is False
