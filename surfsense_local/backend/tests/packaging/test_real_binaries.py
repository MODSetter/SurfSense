"""Build the real API and worker binaries and prove each one boots.

Heavier than test_frozen_boot (torch + Docling), same opt-in marker. That test
proves the database opens in a frozen binary; this proves the two binaries the
installer actually ships start: the API answers /health, the worker imports its
tasks and stays up instead of crashing on a dropped hidden import.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

BACKEND = Path(__file__).resolve().parents[2]
BUNDLING = BACKEND / "bundling"


def _freeze(spec: str, tmp_path: Path) -> Path:
    """Freeze one spec into tmp and return the onedir executable."""
    name = spec.removesuffix(".spec")
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", str(BUNDLING / spec),
            "--noconfirm",
            "--distpath", str(tmp_path / "dist"),
            "--workpath", str(tmp_path / "build"),
        ],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    )
    return tmp_path / "dist" / name / name


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    return {**os.environ, "SURFSENSE_LOCAL_DATA_DIR": str(tmp_path / "data"), **extra}


def test_api_binary_answers_health(tmp_path: Path) -> None:
    """Freeze the API and assert the running binary serves /health."""
    binary = _freeze("api.spec", tmp_path)
    port = _free_port()
    proc = subprocess.Popen(
        [str(binary)],
        env=_env(tmp_path, SURFSENSE_LOCAL_PORT=str(port)),
    )
    try:
        # Frozen cold start (onedir unpack + imports + migrations) is ~20s here,
        # slower on CI, so give it room before calling it dead.
        deadline = time.time() + 90
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"api binary exited early with {proc.returncode}")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1
                ) as reply:
                    assert reply.status == 200
                    return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.5)
        pytest.fail("api binary was not healthy within 90s")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_worker_binary_starts(tmp_path: Path) -> None:
    """Freeze the worker and assert the binary boots without a dropped import."""
    binary = _freeze("worker.spec", tmp_path)
    proc = subprocess.Popen([str(binary)], env=_env(tmp_path))
    try:
        # A dropped hidden import crashes the consumer on startup; staying up for
        # a few seconds is the binary importing its tasks without error.
        time.sleep(5)
        assert proc.poll() is None, f"worker binary exited with {proc.returncode}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
