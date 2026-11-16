"""SURFSENSE_LOCAL_EMBED_PRECISION: by default the bundled bge is upcast on
x86-64 only."""

import platform
import sysconfig

import pytest

from modules.embedding.bundled import BGE
from modules.embedding.precision import runs_at_fp32

pytestmark = pytest.mark.unit

SWITCH = "SURFSENSE_LOCAL_EMBED_PRECISION"


@pytest.mark.parametrize(
    ("switch", "build", "upcast"),
    [
        (None, "win-amd64", True),
        (None, "linux-x86_64", True),
        (None, "macosx-11.0-arm64", False),
        (None, "linux-aarch64", False),
        (None, "win-arm64", False),
        ("auto", "win-amd64", True),
        ("auto", "macosx-11.0-arm64", False),
        ("fp16", "win-amd64", False),
        ("fp32", "macosx-11.0-arm64", True),
        (" FP32 ", "linux-aarch64", True),
        ("int8", "win-amd64", False),
    ],
)
def test_the_switch_picks_the_precision(
    monkeypatch: pytest.MonkeyPatch, switch: str | None, build: str, upcast: bool
) -> None:
    """auto upcasts on an x86-64 build, where FP16 is slow; fp16 is the file as
    shipped; fp32 upcasts anywhere. A value it cannot read keeps the file as shipped."""
    if switch is None:
        monkeypatch.delenv(SWITCH, raising=False)
    else:
        monkeypatch.setenv(SWITCH, switch)
    monkeypatch.setattr(sysconfig, "get_platform", lambda: build)

    assert runs_at_fp32(BGE) is upcast


def test_auto_follows_the_build_not_the_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows on ARM running the x64 build reports ARM64, yet runs the x64 kernels."""
    monkeypatch.delenv(SWITCH, raising=False)
    monkeypatch.setattr(platform, "machine", lambda: "ARM64")
    monkeypatch.setattr(sysconfig, "get_platform", lambda: "win-amd64")

    assert runs_at_fp32(BGE) is True


def test_only_the_bundled_file_is_upcast(monkeypatch: pytest.MonkeyPatch) -> None:
    """Another model's FP16 build was never measured, so even fp32 leaves it be;
    the bundled file under a different prompt is still the bundled file."""
    monkeypatch.setenv(SWITCH, "fp32")

    assert runs_at_fp32(BGE.model_copy(update={"repo": "someone/bge-fork"})) is False
    assert runs_at_fp32(BGE.model_copy(update={"query_prefix": "query: "})) is True
