"""Finding the app's own processes and which engine each one belongs to.

The tree is the Electron shell and everything below it. Each child of the shell
starts a branch, and a whole branch is one engine: llama-server's router spawns
a worker per loaded model, and each Python sidecar is a venv launcher with the
real interpreter under it in development.
"""

import pytest

from modules.resource_usage.app_tree import branches
from modules.resource_usage.engines import Engine, engine_of

pytestmark = pytest.mark.unit

SHELL = 100


def born_in_order(parents: dict[int, int]):
    """Every process born one tick after the one it was listed after."""
    order = {pid: float(index) for index, pid in enumerate([SHELL, *parents])}
    return order.get


def test_each_process_is_filed_under_the_shell_child_that_started_it() -> None:
    """A router worker belongs to llama-server's branch, not the shell's."""
    parents = {
        200: SHELL,  # llama-server, the router
        201: 200,  # llama-server, the worker holding a model
        300: SHELL,  # the venv launcher
        301: 300,  # the interpreter it starts
        999: 1,  # a stranger
    }

    tree = branches(parents, SHELL, born_in_order(parents))

    assert tree == {SHELL: SHELL, 200: 200, 201: 200, 300: 300, 301: 300}


def test_a_stranger_holding_a_dead_parents_pid_is_not_ours() -> None:
    """Windows keeps a dead parent's pid as the child's ppid, and that pid can be
    reused by one of ours. A process older than its supposed parent is the tell."""
    parents = {200: SHELL, 500: 200}
    born = {SHELL: 10.0, 200: 20.0, 500: 5.0}.get

    assert branches(parents, SHELL, born) == {SHELL: SHELL, 200: 200}


def test_a_process_gone_before_its_birth_is_read_is_skipped() -> None:
    """An exit between the snapshot and the read drops the process, not the sample."""
    parents = {200: SHELL, 201: 200}
    born = {SHELL: 1.0, 200: 2.0}.get

    assert branches(parents, SHELL, born) == {SHELL: SHELL, 200: 200}


def test_a_cycle_in_a_torn_snapshot_ends() -> None:
    """The snapshot is taken while pids are reused, so it can loop."""
    parents = {200: SHELL, 201: 200, SHELL: 201}
    born = {SHELL: 1.0, 200: 2.0, 201: 3.0}.get

    assert branches(parents, SHELL, born) == {SHELL: SHELL, 200: 200, 201: 200}


@pytest.mark.parametrize(
    ("executable", "engine"),
    [
        # Windows names, as psutil reported them on the test machine.
        ("llama-server.exe", Engine.LLAMACPP),
        ("sd-server.exe", Engine.SDCPP),
        ("audiocpp_server.exe", Engine.AUDIOCPP),
        ("python.exe", Engine.BACKEND),
        ("electron.exe", Engine.INTERFACE),
        # Packaged: frozen onedir binaries, and the app's own executable.
        ("api.exe", Engine.BACKEND),
        ("worker", Engine.BACKEND),
        ("SurfSense.exe", Engine.INTERFACE),
        ("SurfSense Helper (GPU)", Engine.INTERFACE),
        # POSIX development interpreters carry their version.
        ("python3.12", Engine.BACKEND),
        ("llama-server", Engine.LLAMACPP),
    ],
)
def test_a_branch_is_named_by_the_executable_that_started_it(
    executable: str, engine: Engine
) -> None:
    """Development, packaged and POSIX names all land on the right engine."""
    assert engine_of(executable) is engine
