"""Build the real backend binary and prove each role boots.

Heavier than test_frozen_boot (torch + Docling), same opt-in marker. That test
proves the database opens in a frozen binary; this proves the binary the
installer ships starts in both roles: the API answers /health, the worker
imports its tasks and stays up instead of crashing on a dropped hidden import,
and what the bundle leaves out stays out.
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
from PyInstaller.archive.readers import CArchiveReader

from tests.packaging.frozen_backend import frozen_backend

pytestmark = pytest.mark.packaging


@pytest.fixture(scope="module")
def binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The backend frozen once for this module."""
    return frozen_backend(tmp_path_factory.mktemp("frozen-backend"))


def _internal(binary: Path) -> Path:
    return binary.parent / "_internal"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    return {**os.environ, "SURFSENSE_LOCAL_DATA_DIR": str(tmp_path / "data"), **extra}


def _run(binary: Path, tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess:
    # Bounded: a role that hangs must fail the release job, not stall it.
    try:
        return subprocess.run(
            [str(binary), *arguments],
            env=_env(tmp_path),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"the frozen backend hung with {list(arguments)}")


def test_the_bundle_ships_the_manifests_both_roles_read(binary: Path) -> None:
    """Read by path, so only an explicit datas entry puts them in the bundle.

    Missing them degrades silently, in frozen builds only: every remote model
    reads as unknown, and Studio calls an installed model "not installed".
    """
    manifests = _internal(binary) / "modules" / "llm" / "catalog"
    assert json.loads(
        (manifests / "remote" / "manifest" / "models.json").read_text(encoding="utf-8")
    )["providers"]
    assert json.loads(
        (manifests / "local" / "manifest" / "models.json").read_text(encoding="utf-8")
    )["models"]


def test_no_claude_code_ships(binary: Path) -> None:
    """The SDK's own Claude Code stays out: every run uses the user's (ADR 0057)."""
    shipped = [
        path
        for path in binary.parent.rglob("*")
        if path.name in ("claude", "claude.exe") or "_bundled" in path.parts
    ]
    assert shipped == [], f"Claude Code is in the bundle: {shipped}"


def test_a_launch_without_a_role_starts_nothing(binary: Path, tmp_path: Path) -> None:
    """No default role: a stray launch must not start a server nothing will stop."""
    for arguments in ([], ["serve"], ["worker"], ["api", "extra"]):
        result = _run(binary, tmp_path, *arguments)
        assert result.returncode == 2, (arguments, result.stderr)


def test_the_api_role_answers_health_and_stays_light(
    binary: Path, tmp_path: Path
) -> None:
    """The API serves /health and its catalog, and cannot reach the worker's stack."""
    # /health and /llm/catalog/local never touch retrieval, so a dropped encoder
    # would pass the checks below and only break on a user's first chat.
    retrieval = _run(binary, tmp_path, "--check-retrieval-runtime")
    assert retrieval.returncode == 0, retrieval.stderr
    assert "retrieval imports OK" in retrieval.stdout
    assert "api role imports no worker-only modules" in retrieval.stdout

    port = _free_port()
    proc = subprocess.Popen(
        [str(binary), "api"],
        env=_env(tmp_path, SURFSENSE_LOCAL_PORT=str(port)),
    )
    try:
        # Frozen cold start (onedir unpack + imports + migrations) is ~20s here,
        # slower on CI, so give it room before calling it dead.
        deadline = time.time() + 90
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"api role exited early with {proc.returncode}")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1
                ) as reply:
                    assert reply.status == 200
                # The first catalog read probes the hardware in a child, which
                # starts this binary again: a cold start on a CI runner.
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/llm/catalog/local", timeout=120
                ) as reply:
                    catalog = json.load(reply)
                # The frozen build found and read its packaged manifest.
                assert any(row["origin"] == "curated" for row in catalog["rows"])
                return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.5)
        pytest.fail("api role was not healthy within 90s")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_the_worker_role_starts(binary: Path, tmp_path: Path) -> None:
    """Its lazy vision imports load, and each queue's consumer stays up."""
    vision = _run(binary, tmp_path, "--check-vision-runtime")
    assert vision.returncode == 0, vision.stderr
    assert "vision imports OK" in vision.stdout

    # A dropped hidden import crashes a consumer at startup; staying up is the proof.
    for queue in ("ingest", "studio", "plugins"):
        proc = subprocess.Popen([str(binary), "worker", queue], env=_env(tmp_path))
        try:
            time.sleep(5)
            assert proc.poll() is None, f"{queue} worker exited with {proc.returncode}"
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def test_payload_no_code_path_opens_stays_out(binary: Path) -> None:
    """Each was measured, and each is reached by nothing the app runs."""
    internal = _internal(binary)

    # The parser pack's copy is the one RapidOCR and Docling read.
    assert list((internal / "rapidocr" / "models").glob("*.onnx")) == []
    # onnxruntime's C API library; Python loads only the pybind module.
    capi = internal / "onnxruntime" / "capi"
    assert [
        p.name
        for p in capi.iterdir()
        if p.name.startswith(("onnxruntime.dll", "libonnxruntime."))
    ] == []
    assert list(capi.glob("onnxruntime_pybind11_state*")) != []
    if sys.platform == "win32":
        assert list((internal / "cv2").glob("opencv_videoio_ffmpeg*")) == []
    assert not (internal / "torch" / "test").exists()
    # torch_shm_manager stays where torch has one: `import torch` needs it.
    torch_bin = internal / "torch" / "bin"
    if torch_bin.exists():
        assert {p.name for p in torch_bin.iterdir()} <= {"torch_shm_manager"}
    for package in ("faker", "polyfactory", "_pytest", "hf_xet"):
        assert not (internal / package).exists(), package
    if sys.platform == "win32":
        # pywin32's MFC GUI.
        assert list(internal.rglob("win32ui*.pyd")) == []
        assert list(internal.rglob("mfc140u.dll")) == []
    if sys.platform == "linux":
        # opencv-python-headless: no Qt.
        assert not (internal / "cv2" / "qt").exists()
        test_libraries = {
            "libtorchbind_test.so",
            "libjitbackend_test.so",
            "libbackend_with_compiler.so",
            "libaoti_custom_ops.so",
        }
        assert test_libraries.isdisjoint(
            p.name for p in (internal / "torch" / "lib").iterdir()
        )
    # Only the model families Docling's layout engine loads.
    families = {
        p.name for p in (internal / "transformers" / "models").iterdir() if p.is_dir()
    }
    assert families <= {"auto", "rt_detr", "rt_detr_v2", "encoder_decoder"}, families
    # torch ships as bytecode, but its config modules keep the source they read.
    assert not (internal / "torch" / "nn" / "functional.py").exists()
    assert (internal / "torch" / "_dynamo" / "config.py").exists()


def test_excluded_modules_stay_out_of_the_archive(binary: Path) -> None:
    """Pure Python, so they would ship inside the archive, not as folders."""
    executable = binary.with_suffix(".exe") if sys.platform == "win32" else binary
    archive = CArchiveReader(str(executable)).open_embedded_archive("PYZ.pyz")
    excluded = (
        "pytest",
        "_pytest",
        "faker",
        "polyfactory",
        "hf_xet",
        "win32ui",
        "pywin",
        "onnxruntime.transformers",
        "onnxruntime.quantization",
        "onnxruntime.tools",
    )
    shipped = [
        name
        for name in archive.toc
        if any(name == gone or name.startswith(gone + ".") for gone in excluded)
    ]
    assert shipped == []
    # The layout engine's families still ship, and the analyser found them.
    assert "transformers.models.rt_detr_v2.modeling_rt_detr_v2" in archive.toc
