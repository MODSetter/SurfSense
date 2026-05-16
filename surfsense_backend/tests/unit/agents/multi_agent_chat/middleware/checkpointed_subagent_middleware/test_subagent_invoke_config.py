"""Per-call ``thread_id`` derivation for nested subagent invocations.

Parallel ``task`` (and ``ask_knowledge_base``) calls must land in disjoint
checkpoint slots so their nested pregel runs do not stomp on each other or on
the parent's checkpoint state. The slot key is derived from the runtime's
``tool_call_id`` so the same call across the resume cycle keeps reading from
the same snapshot.

Note: we namespace via ``thread_id`` rather than ``checkpoint_ns`` because
langgraph's ``aget_state`` interprets a non-empty ``checkpoint_ns`` as a
subgraph path and raises ``ValueError("Subgraph X not found")``. ``thread_id``
is the primary checkpoint key and is free-form, so it's the right primitive.
"""

from __future__ import annotations

from langchain.tools import ToolRuntime

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.config import (
    subagent_invoke_config,
)


def _runtime(*, tool_call_id: str, config: dict | None = None) -> ToolRuntime:
    return ToolRuntime(
        state=None,
        context=None,
        config=config or {},
        stream_writer=None,
        tool_call_id=tool_call_id,
        store=None,
    )


class TestSubagentInvokeThreadId:
    def test_sets_per_call_thread_id_under_parent(self):
        runtime = _runtime(
            tool_call_id="tcid-A",
            config={"configurable": {"thread_id": "t1"}},
        )

        sub_config = subagent_invoke_config(runtime)

        assert sub_config["configurable"]["thread_id"] == "t1::task:tcid-A"

    def test_per_call_thread_id_nests_under_already_namespaced_parent(self):
        """A subagent that itself spawns a subagent must keep nesting cleanly."""
        runtime = _runtime(
            tool_call_id="tcid-inner",
            config={
                "configurable": {
                    "thread_id": "t1::task:tcid-outer",
                }
            },
        )

        sub_config = subagent_invoke_config(runtime)

        assert (
            sub_config["configurable"]["thread_id"]
            == "t1::task:tcid-outer::task:tcid-inner"
        )

    def test_different_tool_call_ids_produce_different_thread_ids(self):
        config = {"configurable": {"thread_id": "t1"}}
        rt_a = _runtime(tool_call_id="tcid-A", config=config)
        rt_b = _runtime(tool_call_id="tcid-B", config=config)

        tid_a = subagent_invoke_config(rt_a)["configurable"]["thread_id"]
        tid_b = subagent_invoke_config(rt_b)["configurable"]["thread_id"]

        assert tid_a != tid_b

    def test_same_tool_call_id_produces_same_thread_id_across_repeated_calls(self):
        """Resume bridge needs to find the snapshot it primed earlier."""
        config = {"configurable": {"thread_id": "t1"}}
        rt_first = _runtime(tool_call_id="tcid-A", config=config)
        rt_second = _runtime(tool_call_id="tcid-A", config=config)

        tid_first = subagent_invoke_config(rt_first)["configurable"]["thread_id"]
        tid_second = subagent_invoke_config(rt_second)["configurable"]["thread_id"]

        assert tid_first == tid_second

    def test_does_not_mutate_caller_config(self):
        """Repeated calls must not accumulate suffixes onto the parent's config."""
        original_thread_id = "t1"
        config = {"configurable": {"thread_id": original_thread_id}}
        runtime = _runtime(tool_call_id="tcid-A", config=config)

        subagent_invoke_config(runtime)
        subagent_invoke_config(runtime)

        assert config["configurable"]["thread_id"] == original_thread_id
