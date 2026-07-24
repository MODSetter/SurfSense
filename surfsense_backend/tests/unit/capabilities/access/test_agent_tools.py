"""The agent door (05): generate one LangChain tool per registry verb."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from app.capabilities.core.types import BillingUnit, Capability
from app.services.web_crawl_credit_service import InsufficientCreditsError

pytestmark = pytest.mark.asyncio


class _EchoInput(BaseModel):
    text: str = Field(description="The text to echo back.")


class _EchoOutput(BaseModel):
    echoed: str

    @property
    def billable_units(self) -> int:
        return 1


def _capability(
    *, name: str, output: _EchoOutput, unit=BillingUnit.WEB_CRAWL
) -> Capability:
    async def _executor(payload: _EchoInput) -> _EchoOutput:
        _executor.seen = payload
        return output

    cap = Capability(
        name=name,
        description=f"{name} does a thing.",
        input_schema=_EchoInput,
        output_schema=_EchoOutput,
        executor=_executor,
        billing_unit=unit,
    )
    cap.executor.seen = None  # type: ignore[attr-defined]
    return cap


class _FakeSessionCtx:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def isolate(monkeypatch):
    """Stub the billing session + charge/gate so tools never hit the DB."""
    from app.capabilities.core.access import agent as mod

    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCtx())
    charge = AsyncMock()
    gate = AsyncMock()
    monkeypatch.setattr(mod, "charge_capability", charge)
    monkeypatch.setattr(mod, "gate_capability", gate)
    return SimpleNamespace(module=mod, charge=charge, gate=gate)


def _verb_tool(tools, name: str):
    """Pick one capability tool out of the list (readers are appended after)."""
    return next(t for t in tools if t.name == name)


def _invoke(tool, text: str, *, state=None):
    """Call the coroutine with a stand-in runtime (ToolNode injects it in prod)."""
    runtime = SimpleNamespace(state=state or {}, tool_call_id="tc_1", context=None)
    return tool.coroutine(runtime, text=text)


async def test_registry_becomes_one_tool_per_verb_plus_readers(isolate):
    caps = [
        _capability(name="web.scrape", output=_EchoOutput(echoed="a")),
        _capability(name="web.discover", output=_EchoOutput(echoed="b"), unit=None),
    ]

    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=caps)

    by_name = {t.name: t for t in tools}
    # One tool per verb, plus the shared run-reader tools.
    assert set(by_name) == {
        "web_scrape",
        "web_discover",
        "read_run",
        "search_run",
        "export_run",
    }
    assert by_name["web_scrape"].description == "web.scrape does a thing."
    assert by_name["web_scrape"].args_schema is _EchoInput


async def test_input_field_docs_reach_the_model(isolate):
    """Per-field descriptions must surface in the tool's args schema (LLM context)."""
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="a"))
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    assert tool.args["text"]["description"] == "The text to echo back."


async def test_tool_runs_executor_and_returns_serialized_output(isolate):
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi there"))
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    result = await _invoke(tool, "ping")

    # Fake session makes record_run fail -> no run_id key, plain serialized output.
    assert result == {"echoed": "hi there"}
    assert cap.executor.seen.text == "ping"


async def test_tool_registers_run_citation_when_stored(isolate, monkeypatch):
    from langgraph.types import Command

    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi"))
    monkeypatch.setattr(isolate.module, "record_run", AsyncMock(return_value="abc-123"))
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    result = await _invoke(tool, "ping")

    assert isinstance(result, Command)
    registry = result.update["citation_registry"]
    entry = registry.resolve(1)
    assert entry is not None
    assert entry.locator["run_id"] == "run_abc-123"
    message = result.update["messages"][0]
    assert "[1]" in message.content
    assert "run_abc-123" in message.content


async def test_runtime_survives_langchain_arg_parsing(isolate):
    """runtime must survive langchain arg parsing (else ToolNode drops it)."""
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi"))
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    parsed = tool._parse_input({"text": "x", "runtime": "RT"}, "tc_1")

    assert parsed["runtime"] == "RT"


async def test_tool_charges_owner(isolate):
    output = _EchoOutput(echoed="hi")
    cap = _capability(name="web.scrape", output=output)
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    await _invoke(tool, "ping")

    isolate.charge.assert_awaited_once()
    (charged_output, unit, ctx), _ = isolate.charge.call_args
    assert charged_output is output
    assert unit is BillingUnit.WEB_CRAWL
    assert ctx.workspace_id == 7


async def test_over_budget_returns_friendly_message(isolate):
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi"))
    isolate.gate.side_effect = InsufficientCreditsError(
        message="This run would exceed your available credit.",
        balance_micros=0,
        required_micros=1_000_000,
    )
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    result = await _invoke(tool, "ping")

    assert isinstance(result, str)
    assert "credit" in result.lower()
    assert cap.executor.seen is None
    isolate.charge.assert_not_awaited()
