"""Build the real API and worker binaries and prove each one boots.

Heavier than test_frozen_boot (torch + Docling), same opt-in marker. That test
proves the database opens in a frozen binary; this proves the two binaries the
installer actually ships start: the API answers /health, the worker imports its
tasks and stays up instead of crashing on a dropped hidden import.
"""

import json
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
            sys.executable,
            "-m",
            "PyInstaller",
            str(BUNDLING / spec),
            "--noconfirm",
            "--distpath",
            str(tmp_path / "dist"),
            "--workpath",
            str(tmp_path / "build"),
        ],
        cwd=BACKEND,
        check=True,
        capture_output=True,
        text=True,
    )
    return tmp_path / "dist" / name / name


def _assert_capability_catalogue_shipped(binary: Path) -> None:
    """Both binaries classify remote models, so both must carry the manifest.

    It is read by path, so the analyser cannot see it and only an explicit datas
    entry puts it in the bundle. Missing it degrades silently: every remote model
    reads as unknown, in frozen builds only.
    """
    manifest = (
        binary.parent
        / "_internal"
        / "modules"
        / "llm"
        / "catalog"
        / "remote"
        / "manifest"
        / "models.json"
    )
    assert manifest.is_file(), f"remote model manifest missing from {binary.parent}"
    assert json.loads(manifest.read_text())["providers"]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    return {**os.environ, "SURFSENSE_LOCAL_DATA_DIR": str(tmp_path / "data"), **extra}


def test_api_binary_answers_health(tmp_path: Path) -> None:
    """Freeze the API and assert the running binary serves /health."""
    binary = _freeze("api.spec", tmp_path)
    _assert_capability_catalogue_shipped(binary)

    # /health and /llm/catalog never touch retrieval, so an over-broad exclude in
    # api.spec would pass the checks below and only break on a user's first chat.
    retrieval = subprocess.run(
        [str(binary), "--check-retrieval-runtime"],
        env=_env(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "retrieval imports OK" in retrieval.stdout

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
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/llm/catalog", timeout=10
                ) as reply:
                    catalog = json.load(reply)
                warning_codes = {warning["code"] for warning in catalog["warnings"]}
                assert "missing" in warning_codes
                assert "invalid_curated_models" not in warning_codes
                return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.5)
        pytest.fail("api binary was not healthy within 90s")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_worker_binary_starts(tmp_path: Path) -> None:
    """Freeze the worker and assert its lazy vision imports and consumer boot."""
    binary = _freeze("worker.spec", tmp_path)
    _assert_capability_catalogue_shipped(binary)
    vision = subprocess.run(
        [str(binary), "--check-vision-runtime"],
        env=_env(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "vision imports OK" in vision.stdout

    # A dropped hidden import crashes a consumer at startup; staying up is the proof.
    for queue in ("ingest", "studio"):
        proc = subprocess.Popen([str(binary), queue], env=_env(tmp_path))
        try:
            time.sleep(5)
            assert proc.poll() is None, f"{queue} worker exited with {proc.returncode}"
        finally:
            proc.terminate()
            proc.wait(timeout=10)
