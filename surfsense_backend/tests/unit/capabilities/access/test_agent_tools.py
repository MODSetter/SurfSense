"""The agent door (05): generate one LangChain tool per registry verb."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from app.capabilities.types import BillingUnit, Capability
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
    from app.capabilities.access import agent as mod

    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCtx())
    charge = AsyncMock()
    gate = AsyncMock()
    monkeypatch.setattr(mod, "charge_capability", charge)
    monkeypatch.setattr(mod, "gate_capability", gate)
    return SimpleNamespace(module=mod, charge=charge, gate=gate)


async def test_registry_becomes_one_tool_per_verb(isolate):
    caps = [
        _capability(name="web.scrape", output=_EchoOutput(echoed="a")),
        _capability(name="web.discover", output=_EchoOutput(echoed="b"), unit=None),
    ]

    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=caps)

    by_name = {t.name: t for t in tools}
    assert set(by_name) == {"web_scrape", "web_discover"}
    assert by_name["web_scrape"].description == "web.scrape does a thing."
    assert by_name["web_scrape"].args_schema is _EchoInput


async def test_input_field_docs_reach_the_model(isolate):
    """Per-field descriptions must surface in the tool's args schema (LLM context)."""
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="a"))
    [tool] = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])

    assert tool.args["text"]["description"] == "The text to echo back."


async def test_tool_runs_executor_and_returns_serialized_output(isolate):
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi there"))
    [tool] = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])

    result = await tool.ainvoke({"text": "ping"})

    assert result == {"echoed": "hi there"}
    assert cap.executor.seen.text == "ping"


async def test_tool_charges_owner(isolate):
    output = _EchoOutput(echoed="hi")
    cap = _capability(name="web.scrape", output=output)
    [tool] = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])

    await tool.ainvoke({"text": "ping"})

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
    [tool] = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])

    result = await tool.ainvoke({"text": "ping"})

    assert isinstance(result, str)
    assert "credit" in result.lower()
    assert cap.executor.seen is None
    isolate.charge.assert_not_awaited()
