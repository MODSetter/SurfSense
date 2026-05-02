"""Unit tests for ``POST /threads/{id}/revert-turn/{chat_turn_id}``.

The per-turn batch revert route walks rows in reverse ``created_at``
order, reverts each independently, and returns a per-action result
list. Partial success is normal — the response status
is ``"partial"`` whenever any row could not be reverted, but we never
collapse the whole batch into a 4xx.

These tests stub ``load_thread`` / ``revert_action`` and feed a fake
session, so they exercise the route's dispatch logic without a real DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.routes import agent_revert_route
from app.services.revert_service import RevertOutcome


@dataclass
class _FakeAction:
    id: int
    tool_name: str
    user_id: str | None = "u1"
    reverse_of: int | None = None
    error: dict | None = None


@dataclass
class _FakeUser:
    id: str = "u1"


@dataclass
class _ScalarResult:
    rows: list[Any]

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def all(self) -> list[Any]:
        return list(self.rows)


@dataclass
class _Result:
    rows: list[Any] = field(default_factory=list)

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self.rows)

    def all(self) -> list[Any]:
        # ``_was_already_reverted_batch`` calls ``.all()`` directly on
        # the row-tuple result (no ``.scalars()`` indirection). The
        # rows queued for that helper are list[(revert_id, original_id)].
        return list(self.rows)


class _FakeNestedCtx:
    """Async context manager that mimics ``session.begin_nested()``.

    The route raises a sentinel exception inside this block to roll back
    bad rows. We just pass the exception through.
    """

    async def __aenter__(self) -> _FakeNestedCtx:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        # Returning False (or None) propagates the exception; the route
        # catches its own sentinel above this layer.
        return False


class _FakeSession:
    """Minimal AsyncSession stand-in for the revert-turn route.

    Holds a queue of result objects; each ``execute(...)`` pops the next
    one. The route calls ``execute`` exactly once per query so this maps
    cleanly onto the assertion order of the test.
    """

    def __init__(self) -> None:
        self._results: list[_Result] = []
        self.committed = False
        self.rolled_back = False
        # Count execute() calls to assert "no N+1 reverts".
        self.execute_call_count = 0

    def queue(self, *results: _Result) -> None:
        self._results.extend(results)

    async def execute(self, _stmt: Any) -> _Result:
        self.execute_call_count += 1
        if not self._results:
            return _Result(rows=[])
        return self._results.pop(0)

    def begin_nested(self) -> _FakeNestedCtx:
        return _FakeNestedCtx()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _enabled_flags() -> AgentFeatureFlags:
    return AgentFeatureFlags(
        disable_new_agent_stack=False,
        enable_action_log=True,
        enable_revert_route=True,
    )


@pytest.fixture
def patch_get_flags():
    def _patch(flags: AgentFeatureFlags):
        return patch(
            "app.routes.agent_revert_route.get_flags",
            return_value=flags,
        )

    return _patch


class TestFlagGuard:
    @pytest.mark.asyncio
    async def test_returns_503_when_revert_route_disabled(
        self, patch_get_flags
    ) -> None:
        flags = AgentFeatureFlags(
            disable_new_agent_stack=False,
            enable_action_log=True,
            enable_revert_route=False,
        )
        session = _FakeSession()
        with patch_get_flags(flags), pytest.raises(Exception) as exc:
            await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="42:1700000000000",
                session=session,
                user=_FakeUser(),
            )
        assert getattr(exc.value, "status_code", None) == 503


class TestRevertTurnDispatch:
    @pytest.mark.asyncio
    async def test_empty_turn_returns_ok_with_no_rows(self, patch_get_flags) -> None:
        session = _FakeSession()
        session.queue(_Result(rows=[]))  # rows query returns nothing
        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-empty",
                session=session,
                user=_FakeUser(),
            )
        assert response.status == "ok"
        assert response.total == 0
        assert response.results == []
        assert session.committed is True

    @pytest.mark.asyncio
    async def test_walks_rows_in_reverse_and_reverts_each(
        self, patch_get_flags
    ) -> None:
        rows = [
            _FakeAction(id=10, tool_name="rm"),
            _FakeAction(id=9, tool_name="write_file"),
            _FakeAction(id=8, tool_name="mkdir"),
        ]
        session = _FakeSession()
        session.queue(_Result(rows=rows))
        # Single batched ``_was_already_reverted_batch`` probe replaces
        # the previous N per-row SELECTs.
        session.queue(_Result(rows=[]))

        async def _fake_revert(_session, *, action, requester_user_id):
            return RevertOutcome(
                status="ok",
                message=f"reverted-{action.id}",
                new_action_id=100 + action.id,
            )

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(
                agent_revert_route, "revert_action", AsyncMock(side_effect=_fake_revert)
            ),
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-3",
                session=session,
                user=_FakeUser(),
            )

        assert response.status == "ok"
        assert response.total == 3
        assert response.reverted == 3
        assert [r.action_id for r in response.results] == [10, 9, 8]
        assert all(r.status == "reverted" for r in response.results)
        assert response.results[0].new_action_id == 110
        # Only TWO ``execute`` calls regardless of the row count: one
        # for the rows query, one for the batched
        # ``_was_already_reverted_batch`` probe. Regression guard
        # against re-introducing the per-row N+1 lookup.
        assert session.execute_call_count == 2, (
            "revert-turn loop must batch idempotency probes; got "
            f"{session.execute_call_count} execute() calls (expected 2)."
        )

    @pytest.mark.asyncio
    async def test_already_reverted_rows_are_marked_idempotent(
        self, patch_get_flags
    ) -> None:
        rows = [_FakeAction(id=5, tool_name="edit_file")]
        session = _FakeSession()
        session.queue(_Result(rows=rows))
        # Batch probe returns ``[(revert_id, original_id)]``.
        session.queue(_Result(rows=[(42, 5)]))

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(agent_revert_route, "revert_action", AsyncMock()) as revert,
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-i",
                session=session,
                user=_FakeUser(),
            )
        assert response.status == "ok"
        assert response.already_reverted == 1
        assert response.results[0].status == "already_reverted"
        assert response.results[0].new_action_id == 42
        revert.assert_not_called()

    @pytest.mark.asyncio
    async def test_revert_action_skips_existing_revert_rows(
        self, patch_get_flags
    ) -> None:
        rows = [_FakeAction(id=99, tool_name="_revert:edit_file", reverse_of=42)]
        session = _FakeSession()
        session.queue(_Result(rows=rows))

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(agent_revert_route, "revert_action", AsyncMock()) as revert,
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-rev",
                session=session,
                user=_FakeUser(),
            )
        assert response.status == "ok"
        assert response.results[0].status == "skipped"
        revert.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_success_when_some_rows_not_reversible(
        self, patch_get_flags
    ) -> None:
        rows = [
            _FakeAction(id=2, tool_name="send_email"),
            _FakeAction(id=1, tool_name="edit_file"),
        ]
        session = _FakeSession()
        session.queue(_Result(rows=rows))
        # Single batched idempotency probe.
        session.queue(_Result(rows=[]))

        async def _fake_revert(_session, *, action, requester_user_id):
            if action.tool_name == "send_email":
                return RevertOutcome(
                    status="not_reversible",
                    message="connector revert not yet implemented",
                )
            return RevertOutcome(status="ok", message="ok", new_action_id=500)

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(
                agent_revert_route, "revert_action", AsyncMock(side_effect=_fake_revert)
            ),
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-mix",
                session=session,
                user=_FakeUser(),
            )
        assert response.status == "partial"
        assert response.reverted == 1
        assert response.not_reversible == 1
        statuses = sorted(r.status for r in response.results)
        assert statuses == ["not_reversible", "reverted"]

    @pytest.mark.asyncio
    async def test_unexpected_exception_marks_row_failed_not_batch(
        self, patch_get_flags
    ) -> None:
        rows = [
            _FakeAction(id=20, tool_name="edit_file"),
            _FakeAction(id=21, tool_name="edit_file"),
        ]
        session = _FakeSession()
        session.queue(_Result(rows=rows))
        # Single batched idempotency probe.
        session.queue(_Result(rows=[]))

        async def _fake_revert(_session, *, action, requester_user_id):
            if action.id == 20:
                raise RuntimeError("disk on fire")
            return RevertOutcome(status="ok", message="ok", new_action_id=999)

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(
                agent_revert_route, "revert_action", AsyncMock(side_effect=_fake_revert)
            ),
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-fail",
                session=session,
                user=_FakeUser(),
            )
        assert response.status == "partial"
        assert response.failed == 1
        assert response.reverted == 1
        bad = next(r for r in response.results if r.action_id == 20)
        assert bad.status == "failed"
        assert "disk on fire" in (bad.error or "")
        good = next(r for r in response.results if r.action_id == 21)
        assert good.status == "reverted"

    @pytest.mark.asyncio
    async def test_permission_denied_when_other_user_owns_action(
        self, patch_get_flags
    ) -> None:
        rows = [_FakeAction(id=7, tool_name="edit_file", user_id="someone-else")]
        session = _FakeSession()
        session.queue(_Result(rows=rows))
        # Batch idempotency probe (no prior reverts).
        session.queue(_Result(rows=[]))

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(agent_revert_route, "revert_action", AsyncMock()) as revert,
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-perm",
                session=session,
                user=_FakeUser(id="not-owner"),
            )
        assert response.status == "partial"
        assert response.results[0].status == "permission_denied"
        # ``permission_denied`` has its own dedicated counter so the
        # response invariant ``total == sum(counters)`` always holds
        # without overloading ``not_reversible`` (which historically
        # absorbed this case and confused frontend toasts).
        assert response.permission_denied == 1
        assert response.not_reversible == 0
        revert.assert_not_called()

    @pytest.mark.asyncio
    async def test_counter_invariant_holds_across_mixed_outcomes(
        self, patch_get_flags
    ) -> None:
        """Every row is accounted for in EXACTLY ONE counter.

        Mixes one of every supported outcome (reverted, already_reverted,
        not_reversible, permission_denied, failed, skipped) and asserts
        that the sum of counters equals ``response.total``.
        """
        rows = [
            _FakeAction(id=10, tool_name="edit_file"),  # ok
            _FakeAction(id=9, tool_name="edit_file"),  # already_reverted
            _FakeAction(id=8, tool_name="send_email"),  # not_reversible
            _FakeAction(id=7, tool_name="rm", user_id="other"),  # permission_denied
            _FakeAction(id=6, tool_name="edit_file"),  # failed
            _FakeAction(id=5, tool_name="_revert:edit_file", reverse_of=99),  # skipped
        ]
        session = _FakeSession()
        session.queue(_Result(rows=rows))
        # Single batched probe; only id=9 has a prior revert.
        # Schema: list[(revert_id, original_id)].
        session.queue(_Result(rows=[(42, 9)]))

        async def _fake_revert(_session, *, action, requester_user_id):
            if action.id == 10:
                return RevertOutcome(status="ok", message="ok", new_action_id=500)
            if action.id == 8:
                return RevertOutcome(
                    status="not_reversible",
                    message="connector revert not yet implemented",
                )
            if action.id == 6:
                raise RuntimeError("boom")
            raise AssertionError(f"unexpected revert call for {action.id}")

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(
                agent_revert_route,
                "revert_action",
                AsyncMock(side_effect=_fake_revert),
            ),
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-mixed-all",
                session=session,
                user=_FakeUser(),  # only id=7 has a different user_id
            )

        assert response.total == len(rows) == 6
        bucket_sum = (
            response.reverted
            + response.already_reverted
            + response.not_reversible
            + response.permission_denied
            + response.failed
            + response.skipped
        )
        assert bucket_sum == response.total, (
            "Counter invariant broken: total "
            f"({response.total}) != sum of counters ({bucket_sum}). "
            f"Counters: reverted={response.reverted}, "
            f"already_reverted={response.already_reverted}, "
            f"not_reversible={response.not_reversible}, "
            f"permission_denied={response.permission_denied}, "
            f"failed={response.failed}, skipped={response.skipped}"
        )
        assert response.reverted == 1
        assert response.already_reverted == 1
        assert response.not_reversible == 1
        assert response.permission_denied == 1
        assert response.failed == 1
        assert response.skipped == 1

    @pytest.mark.asyncio
    async def test_integrity_error_translates_to_already_reverted(
        self, patch_get_flags
    ) -> None:
        """The partial unique index on ``reverse_of`` raises
        ``IntegrityError`` when a concurrent revert wins the race against
        the pre-flight ``_was_already_reverted`` SELECT. The route MUST
        recover by re-querying for the winning revert id and returning
        ``status="already_reverted"`` (not ``"failed"``) so racing
        clients see consistent idempotent semantics.
        """
        from sqlalchemy.exc import IntegrityError

        rows = [_FakeAction(id=33, tool_name="edit_file")]
        session = _FakeSession()
        session.queue(_Result(rows=rows))
        # Batch pre-flight probe: nothing yet (we'll race).
        session.queue(_Result(rows=[]))
        # Post-IntegrityError fallback uses the SCALAR
        # ``_was_already_reverted`` (single-id lookup) so it pulls
        # ``[777]`` via ``.scalars().first()``.
        session.queue(_Result(rows=[777]))

        async def _racing_revert(_session, *, action, requester_user_id):
            raise IntegrityError("INSERT", {}, Exception("dup reverse_of"))

        with (
            patch_get_flags(_enabled_flags()),
            patch.object(
                agent_revert_route, "load_thread", AsyncMock(return_value=object())
            ),
            patch.object(
                agent_revert_route,
                "revert_action",
                AsyncMock(side_effect=_racing_revert),
            ),
        ):
            response = await agent_revert_route.revert_agent_turn(
                thread_id=1,
                chat_turn_id="ct-race",
                session=session,
                user=_FakeUser(),
            )

        assert response.failed == 0, (
            "IntegrityError must NOT surface as a failed row; the unique "
            "index is the durable expression of idempotency."
        )
        assert response.already_reverted == 1
        assert response.results[0].status == "already_reverted"
        assert response.results[0].new_action_id == 777
