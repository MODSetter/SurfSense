"""Registry behaviour that no provider can be trusted to enforce."""

from __future__ import annotations

import asyncio

import pytest

from app.sandbox.protocol import ExecResult, SandboxUnavailableError
from app.sandbox.registry import SandboxRegistry


class FakeSession:
    def __init__(self, thread_id: str) -> None:
        self.session_id = thread_id
        self.terminated = False

    async def execute(self, code: str, language: str = "python") -> ExecResult:
        return ExecResult(output="", exit_code=0)

    async def run_command(self, command: str) -> ExecResult:
        return ExecResult(output="", exit_code=0)

    async def read_file(self, path: str) -> bytes:
        return b""

    async def write_file(self, path: str, data: bytes) -> None:
        return None

    async def terminate(self) -> None:
        self.terminated = True


class FakeProvider:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.terminated: list[str] = []

    async def get_or_create_session(self, thread_id: str) -> FakeSession:
        self.created.append(thread_id)
        return FakeSession(thread_id)

    async def terminate_session(self, thread_id: str) -> None:
        self.terminated.append(thread_id)


async def test_disabled_deployment_refuses_before_building_a_provider(monkeypatch):
    import app.sandbox.registry as registry_module

    def unreachable() -> None:
        raise AssertionError("provider built with code execution disabled")

    monkeypatch.setattr(registry_module.app_config, "SANDBOX_ENABLED", False)
    monkeypatch.setattr("app.sandbox.factory.build_provider", unreachable)

    with pytest.raises(SandboxUnavailableError, match="disabled"):
        await registry_module.get_registry()


async def test_session_is_reused_within_a_thread():
    provider = FakeProvider()
    registry = SandboxRegistry(provider)

    first = await registry.get_session("t1", "w1")
    second = await registry.get_session("t1", "w1")

    assert first is second
    assert provider.created == ["t1"]


async def test_workspace_cap_rejects_rather_than_queues():
    provider = FakeProvider()
    registry = SandboxRegistry(provider, max_sessions_per_workspace=2)

    await registry.get_session("t1", "w1")
    await registry.get_session("t2", "w1")
    # A different workspace is unaffected by w1's usage.
    await registry.get_session("t3", "w2")

    with pytest.raises(SandboxUnavailableError):
        await registry.get_session("t4", "w1")


async def test_workspace_cap_is_atomic_across_concurrent_threads():
    class BlockingProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def get_or_create_session(self, thread_id: str) -> FakeSession:
            self.started.set()
            await self.release.wait()
            return await super().get_or_create_session(thread_id)

    provider = BlockingProvider()
    registry = SandboxRegistry(provider, max_sessions_per_workspace=1)
    first = asyncio.create_task(registry.get_session("t1", "w1"))
    await provider.started.wait()
    second = asyncio.create_task(registry.get_session("t2", "w1"))
    provider.release.set()

    results = await asyncio.gather(first, second, return_exceptions=True)

    assert sum(isinstance(result, FakeSession) for result in results) == 1
    assert sum(isinstance(result, SandboxUnavailableError) for result in results) == 1


async def test_idle_sessions_are_reaped_and_killed():
    provider = FakeProvider()
    registry = SandboxRegistry(provider, idle_ttl_seconds=0)

    stale = await registry.get_session("t1", "w1")
    # Zero TTL means the next access sees t1 as idle; the cap would trip here
    # if reaping did not run first.
    await registry.get_session("t2", "w1")
    await registry.aclose()

    assert stale.terminated is True
    fresh = await registry.get_session("t1", "w1")
    assert fresh is not stale


async def test_evict_forgets_without_killing():
    provider = FakeProvider()
    registry = SandboxRegistry(provider)

    session = await registry.get_session("t1", "w1")
    await registry.evict("t1")

    assert session.terminated is False
    assert await registry.get_session("t1", "w1") is not session


async def test_terminate_is_safe_when_no_session_exists():
    provider = FakeProvider()
    registry = SandboxRegistry(provider)

    await registry.terminate("never-used")

    assert provider.terminated == ["never-used"]
