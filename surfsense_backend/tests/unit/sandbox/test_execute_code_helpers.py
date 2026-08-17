"""Failure handling in the execute_code tool wrapper."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.tools.execute_code import (
    helpers,
)
from app.config import config as app_config
from app.sandbox import ExecResult, SandboxUnavailableError


class FakeSession:
    def __init__(self, outcomes: list) -> None:
        self._outcomes = list(outcomes)

    async def execute(self, code: str, language: str = "python") -> ExecResult:
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return await outcome()
        return outcome


class FakeRegistry:
    def __init__(self, session: FakeSession | BaseException) -> None:
        self._session = session
        self.terminated: list[str] = []

    async def get_session(self, thread_id, workspace_id):
        if isinstance(self._session, BaseException):
            raise self._session
        return self._session

    async def terminate(self, thread_id) -> None:
        self.terminated.append(str(thread_id))


@pytest.fixture
def middleware():
    return SimpleNamespace(_thread_id="t1", _workspace_id=7)


def _install(monkeypatch, registry: FakeRegistry) -> None:
    async def _get_registry():
        return registry

    monkeypatch.setattr(helpers, "get_registry", _get_registry)


def test_execute_code_uses_the_shared_sandbox_operation_budget():
    assert (
        helpers.MAX_EXECUTE_TIMEOUT
        == app_config.SANDBOX_OPERATION_TIMEOUT_SECONDS
    )


async def test_successful_run_reports_exit_code(monkeypatch, middleware):
    registry = FakeRegistry(FakeSession([ExecResult(output="42", exit_code=0)]))
    _install(monkeypatch, registry)

    out = await helpers.execute_in_sandbox(middleware, "print(42)", None, None)

    assert "42" in out
    assert "exit code 0" in out
    assert registry.terminated == []


async def test_failure_is_retried_once_on_a_fresh_sandbox(monkeypatch, middleware):
    registry = FakeRegistry(
        FakeSession([RuntimeError("kernel gone"), ExecResult(output="ok", exit_code=0)])
    )
    _install(monkeypatch, registry)

    out = await helpers.execute_in_sandbox(middleware, "print(1)", None, None)

    assert "ok" in out
    # The wedged session must be killed, not reused, before the retry.
    assert registry.terminated == ["t1"]


async def test_second_failure_surfaces_a_usable_message(monkeypatch, middleware):
    registry = FakeRegistry(
        FakeSession([RuntimeError("boom"), RuntimeError("boom again")])
    )
    _install(monkeypatch, registry)

    out = await helpers.execute_in_sandbox(middleware, "print(1)", None, None)

    assert out.startswith("Error:")
    assert "temporarily unavailable" in out


async def test_capacity_error_is_not_retried(monkeypatch, middleware):
    registry = FakeRegistry(SandboxUnavailableError("Sandbox limit reached — retry"))
    _install(monkeypatch, registry)

    out = await helpers.execute_in_sandbox(middleware, "print(1)", None, None)

    assert "Sandbox limit reached" in out
    assert registry.terminated == []


async def test_timeout_is_reported_rather_than_retried(monkeypatch, middleware):
    async def _hang() -> ExecResult:
        await asyncio.sleep(5)
        return ExecResult(output="never", exit_code=0)

    registry = FakeRegistry(FakeSession([_hang]))
    _install(monkeypatch, registry)

    out = await helpers.execute_in_sandbox(middleware, "sleep(5)", None, timeout=1)

    assert "exceeded 1s" in out
    assert registry.terminated == []


async def test_silent_success_tells_the_model_to_print(monkeypatch, middleware):
    registry = FakeRegistry(FakeSession([ExecResult(output="", exit_code=0)]))
    _install(monkeypatch, registry)

    out = await helpers.execute_in_sandbox(middleware, "1 + 1", None, None)

    assert "print()" in out
