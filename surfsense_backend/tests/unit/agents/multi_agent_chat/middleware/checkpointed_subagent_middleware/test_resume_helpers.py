"""Resume side-channel is keyed per ``tool_call_id`` so parallel siblings can resume independently."""

from __future__ import annotations

from langchain.tools import ToolRuntime

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.config import (
    consume_surfsense_resume,
    has_surfsense_resume,
)


def _runtime_with_config(
    config: dict, *, tool_call_id: str = "tcid-test"
) -> ToolRuntime:
    return ToolRuntime(
        state=None,
        context=None,
        config=config,
        stream_writer=None,
        tool_call_id=tool_call_id,
        store=None,
    )


class TestConsumeSurfsenseResume:
    def test_pops_only_entry_matching_runtime_tool_call_id(self):
        configurable = {
            "surfsense_resume_value": {
                "tcid-A": {"decisions": ["approve"]},
                "tcid-B": {"decisions": ["reject"]},
            }
        }
        runtime = _runtime_with_config(
            {"configurable": configurable}, tool_call_id="tcid-A"
        )

        assert consume_surfsense_resume(runtime) == {"decisions": ["approve"]}

    def test_popping_one_entry_leaves_siblings_untouched(self):
        configurable = {
            "surfsense_resume_value": {
                "tcid-A": {"decisions": ["approve"]},
                "tcid-B": {"decisions": ["reject"]},
            }
        }
        runtime_a = _runtime_with_config(
            {"configurable": configurable}, tool_call_id="tcid-A"
        )

        consume_surfsense_resume(runtime_a)

        assert configurable["surfsense_resume_value"] == {
            "tcid-B": {"decisions": ["reject"]}
        }

    def test_returns_none_when_no_entry_for_this_tool_call(self):
        runtime = _runtime_with_config(
            {
                "configurable": {
                    "surfsense_resume_value": {"tcid-other": {"decisions": []}}
                }
            },
            tool_call_id="tcid-A",
        )

        assert consume_surfsense_resume(runtime) is None

    def test_returns_none_when_no_payload_queued(self):
        runtime = _runtime_with_config({"configurable": {}})

        assert consume_surfsense_resume(runtime) is None

    def test_returns_none_when_configurable_missing(self):
        runtime = _runtime_with_config({})

        assert consume_surfsense_resume(runtime) is None

    def test_drops_empty_dict_after_last_entry_consumed(self):
        configurable = {
            "surfsense_resume_value": {"tcid-A": {"decisions": ["approve"]}}
        }
        runtime = _runtime_with_config(
            {"configurable": configurable}, tool_call_id="tcid-A"
        )

        consume_surfsense_resume(runtime)

        assert "surfsense_resume_value" not in configurable


class TestHasSurfsenseResume:
    def test_true_when_entry_for_this_tool_call_present(self):
        runtime = _runtime_with_config(
            {
                "configurable": {
                    "surfsense_resume_value": {"tcid-A": {"decisions": ["approve"]}}
                }
            },
            tool_call_id="tcid-A",
        )

        assert has_surfsense_resume(runtime) is True

    def test_false_when_entry_for_other_tool_call_only(self):
        runtime = _runtime_with_config(
            {
                "configurable": {
                    "surfsense_resume_value": {"tcid-other": {"decisions": []}}
                }
            },
            tool_call_id="tcid-A",
        )

        assert has_surfsense_resume(runtime) is False

    def test_does_not_consume_payload(self):
        configurable = {
            "surfsense_resume_value": {"tcid-A": {"decisions": ["approve"]}}
        }
        runtime = _runtime_with_config(
            {"configurable": configurable}, tool_call_id="tcid-A"
        )

        has_surfsense_resume(runtime)

        assert configurable["surfsense_resume_value"] == {
            "tcid-A": {"decisions": ["approve"]}
        }

    def test_false_when_payload_absent(self):
        runtime = _runtime_with_config({"configurable": {}})

        assert has_surfsense_resume(runtime) is False
