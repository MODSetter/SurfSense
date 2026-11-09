"""A Redis for tests: CI's service from REDIS_URL, or a throwaway redis-server."""

import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest


@contextmanager
def redis_url(folder: Path) -> Iterator[str]:
    if url := os.environ.get("REDIS_URL"):
        yield url
        return
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("no redis-server; set REDIS_URL to run against one")
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    server = subprocess.Popen(
        [binary, "--port", str(port), "--save", "", "--dir", str(folder)],
        stdout=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
                break
            except OSError:
                time.sleep(0.05)
        yield f"redis://127.0.0.1:{port}/0"
    finally:
        server.terminate()
        server.wait()


class RestartableRedis:
    """A redis-server the test can stop and start again on the same port."""

    def __init__(self, binary: str, folder: Path) -> None:
        self._binary = binary
        self._folder = folder
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self.url = f"redis://127.0.0.1:{self.port}/0"
        self._server: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        self._server = subprocess.Popen(
            [
                self._binary,
                "--port",
                str(self.port),
                "--save",
                "",
                "--dir",
                str(self._folder),
            ],
            stdout=subprocess.DEVNULL,
        )
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.1).close()
                return
            except OSError:
                time.sleep(0.05)

    def stop(self) -> None:
        if self._server is not None:
            self._server.terminate()
            self._server.wait()
            self._server = None


@contextmanager
def restartable_redis(folder: Path) -> Iterator[RestartableRedis]:
    """Needs the redis-server binary: CI's Redis is a service it cannot restart."""
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("no redis-server to restart")
    server = RestartableRedis(binary, folder)
    server.start()
    try:
        yield server
    finally:
        server.stop()
