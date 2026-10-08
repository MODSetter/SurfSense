"""Parallel lanes take ports from blocks of their own, so one lane's opencode never binds another's port."""

import socket

import pytest

from tests.integration import conftest as integration
from tests.live import conftest as live_conftest
from tests.live import lane_ports
from tests.live.lane_ports import PortBlock, lane_block_base

pytestmark = pytest.mark.unit

# Lanes far past any a sweep runs, so a sweep running beside these tests holds none of their ports.
FAR = 100


def test_two_lanes_never_hand_out_the_same_port() -> None:
    """Two lanes' blocks do not overlap."""
    first = PortBlock(lane_block_base(FAR + 1), size=20)
    second = PortBlock(lane_block_base(FAR + 2), size=20)

    taken = [first.next() for _ in range(10)] + [second.next() for _ in range(10)]

    assert len(set(taken)) == 20
    assert all(40_100 <= p < 40_120 for p in taken[:10])
    assert all(40_200 <= p < 40_220 for p in taken[10:])


def test_a_port_already_bound_is_passed_over() -> None:
    """A port something else holds is skipped, not handed out."""
    block = PortBlock(lane_block_base(FAR + 3), size=5)
    with socket.socket() as held:
        held.bind(("127.0.0.1", block.base))
        held.listen()

        assert block.next() == block.base + 1


def test_a_block_with_nothing_left_says_so() -> None:
    """A spent block fails loudly rather than reusing a port."""
    block = PortBlock(lane_block_base(FAR + 4), size=1)
    block.next()

    with pytest.raises(RuntimeError, match="no free port"):
        block.next()


def test_the_lane_base_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner sets the block; a run without one binds any free port."""
    monkeypatch.setenv("SURFSENSE_LIVE_PORT_BASE", str(lane_block_base(FAR + 5)))

    assert 40_500 <= lane_ports.free_port() < 40_600

    monkeypatch.delenv("SURFSENSE_LIVE_PORT_BASE")
    assert lane_ports.free_port() > 0


def test_the_live_fixtures_take_their_ports_from_the_lane() -> None:
    """The app's uvicorn port and opencode's both come from the lane's block."""
    assert live_conftest.free_port is lane_ports.free_port
    assert integration._free_port is lane_ports.free_port
