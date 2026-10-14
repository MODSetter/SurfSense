"""Ports for a live run's app and opencode from its lane's own block, so parallel lanes never pick the same one.

`free_port()` elsewhere binds port 0 and lets go; seconds later opencode or
uvicorn binds the number, and another lane (or any outgoing connection) can
take it between. A block per lane below the Windows dynamic range (49152 and
up) removes both. SURFSENSE_LIVE_PORT_BASE names the block; unset, any free
port is used as before.
"""

import os
import socket
import threading

PORT_BASE_ENV = "SURFSENSE_LIVE_PORT_BASE"
BLOCK_SIZE = 100


class PortBlock:
    """Hands out the ports of [base, base + size) that bind now, each once per process."""

    def __init__(self, base: int, size: int = BLOCK_SIZE) -> None:
        self.base, self.size = base, size
        self._given: set[int] = set()
        self._lock = threading.Lock()

    def next(self) -> int:
        with self._lock:
            for port in range(self.base, self.base + self.size):
                if port not in self._given and _binds(port):
                    self._given.add(port)
                    return port
        raise RuntimeError(
            f"no free port left in {self.base}-{self.base + self.size - 1}"
        )


def _binds(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def lane_block_base(lane: int, first: int = 30_000) -> int:
    """Lane n's block: 30000 + 100 n, below the Windows dynamic range and its Hyper-V exclusions."""
    return first + BLOCK_SIZE * lane


_block: PortBlock | None = None


def free_port() -> int:
    """A port from this lane's block, or any free loopback port when no lane is set."""
    global _block
    base = os.environ.get(PORT_BASE_ENV)
    if not base:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]
    if _block is None or _block.base != int(base):
        _block = PortBlock(int(base))
    return _block.next()
