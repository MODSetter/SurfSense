import json
from pathlib import Path

import pytest

from modules.llm.recommendations.llmfit import (
    CACHE_VERSION,
    LlmfitAdvisor,
    _fallback_ollama_name,
    _gguf_sources,
    _parse_model,
)
from modules.llm.recommendations.types import FitLevel

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).parents[3] / "fixtures" / "llmfit"


def _executable(tmp_path: Path, body: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "llmfit"
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(0o755)
    return path


def _stub(tmp_path: Path, system: dict, fit: dict, *, log: Path | None = None) -> Path:
    """A fake llmfit that serves fixed `system`/`fit` JSON and, if `log` is
    given, appends every subcommand it's asked to run — so a test can assert
    the expensive `fit` call did or didn't happen."""
    system_json = json.dumps(system)
    fit_json = json.dumps(fit)
    log_line = (
        f"open({str(log)!r}, 'a').write(' '.join(sys.argv[1:]) + chr(10))\n"
        if log is not None
        else ""
    )
    return _executable(
        tmp_path,
        f"""
import sys
{log_line}
if "--version" in sys.argv:
    print("llmfit 1.1.11")
elif "system" in sys.argv:
    print({system_json!r})
else:
    print({fit_json!r})
""",
    )


async def test_adapter_normalizes_the_pinned_cli_contract(tmp_path: Path) -> None:
    """CLI labels, null estimates, and future fields normalize at one seam."""
    system = json.loads((FIXTURES / "system.json").read_text())
    fit = json.loads((FIXTURES / "fit.json").read_text())
    executable = _executable(
        tmp_path,
        f"""
import sys
if "--version" in sys.argv:
    print("llmfit 1.1.11")
elif "system" in sys.argv:
    print({json.dumps(system)!r})
elif "-n" in sys.argv or "--limit" in sys.argv:
    print("unexpected result limit", file=sys.stderr)
    sys.exit(2)
else:
    print({json.dumps(fit)!r})
""",
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 2).scan(8192, refresh=True)

    assert result.warnings == ()
    assert result.scanned is True
    assert result.system is not None
    assert result.system.unified_memory is True
    assert [model.fit for model in result.models] == [
        FitLevel.GOOD,
        FitLevel.PERFECT,
    ]
    assert result.models[0].publisher == "Qwen"
    assert result.models[0].prefill_tps is None
    assert result.models[0].capability_ids == ("tool_use",)


async def test_missing_binary_degrades_to_a_warning(tmp_path: Path) -> None:
    """A missing optional advisor cannot prevent the API from starting."""
    result = await LlmfitAdvisor(tmp_path / "missing", "1.1.11", 1).scan(
        8192, refresh=True
    )

    assert result.models == ()
    assert result.scanned is True
    assert result.warnings[0].code == "missing"


async def test_version_drift_refuses_to_parse_unknown_output(tmp_path: Path) -> None:
    """A binary upgrade requires fixture review before recommendations resume."""
    executable = _executable(tmp_path, 'print("llmfit 2.0.0")\n')

    result = await LlmfitAdvisor(executable, "1.1.11", 1).scan(8192, refresh=True)

    assert result.models == ()
    assert result.warnings[0].code == "version_mismatch"


async def test_timeout_kills_the_process(tmp_path: Path) -> None:
    """A hung hardware probe returns promptly instead of leaking a child."""
    executable = _executable(
        tmp_path,
        "import time\ntime.sleep(10)\n",
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 0.01).scan(8192, refresh=True)

    assert result.warnings[0].code == "timeout"


async def test_malformed_json_is_not_partially_accepted(tmp_path: Path) -> None:
    """Malformed advisor output returns no recommendations."""
    executable = _executable(
        tmp_path,
        """
import sys
print("llmfit 1.1.11" if "--version" in sys.argv else "{not-json")
""",
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 2).scan(8192, refresh=True)

    assert result.models == ()
    assert result.warnings[0].code == "invalid_output"


async def test_nonzero_exit_is_a_scan_warning(tmp_path: Path) -> None:
    """Advisor diagnostics stay in logs while the public API gets a safe warning."""
    executable = _executable(
        tmp_path,
        'import sys\nprint("probe failed", file=sys.stderr)\nsys.exit(2)\n',
    )

    result = await LlmfitAdvisor(executable, "1.1.11", 1).scan(8192, refresh=True)

    assert result.models == ()
    assert result.warnings[0].code == "scan_failed"


# --- gguf_sources / hf.co fallback (Phase 1) -------------------------------


def _row(**overrides: object) -> dict:
    """A raw llmfit fit-result row, defaulting to a trusted-quant native model."""
    base = {
        "name": "org/Some-Model-7B",
        "fit_level": "perfect",
        "provider": "org",
        "runtime": "llama.cpp",
        "best_quant": "Q4_K_M",
        "ollama_name": None,
        "gguf_sources": [],
    }
    return {**base, **overrides}


def test_gguf_sources_dict_entries_parse_into_repo_strings() -> None:
    """Real llmfit output is a list of {provider, repo} dicts, not strings."""
    assert _gguf_sources(
        [{"provider": "bartowski", "repo": "bartowski/Model-GGUF"}]
    ) == ("bartowski/Model-GGUF",)


def test_gguf_sources_tolerates_malformed_entries() -> None:
    """Malformed gguf_sources shapes are ignored, never raised on."""
    assert _gguf_sources("not-a-list") == ()
    assert _gguf_sources([{"provider": "x"}]) == ()  # missing repo
    assert _gguf_sources(["a-bare-string"]) == ()  # not a dict
    assert _gguf_sources(None) == ()


def test_fallback_name_used_only_when_native_name_is_absent() -> None:
    """A native ollama_name always wins over the gguf_sources fallback."""
    model = _parse_model(
        _row(ollama_name="org:tag", gguf_sources=[{"repo": "org/Model-GGUF"}])
    )
    assert model.ollama_name == "org:tag"


def test_fallback_name_trusts_quant_only_for_llamacpp_runtime() -> None:
    """An untrusted quant gets an explicit `:latest`, not a bare tag.

    Ollama silently stores a tag-less `hf.co/<repo>` pull as `:latest` on
    disk — requesting it explicitly keeps `ollama_name` identical to what a
    later `/api/tags` lookup reports, so install verification and "already
    installed" detection on a rescan don't permanently mismatch.
    """
    trusted = _parse_model(
        _row(
            runtime="llama.cpp",
            best_quant="Q8_0",
            gguf_sources=[{"repo": "org/Model-GGUF"}],
        )
    )
    assert trusted.ollama_name == "hf.co/org/Model-GGUF:Q8_0"
    assert trusted.fit is FitLevel.PERFECT  # unchanged: quant is trustworthy

    untrusted = _parse_model(
        _row(
            runtime="MLX",
            best_quant="mlx-4bit",
            gguf_sources=[{"repo": "org/Model-GGUF"}],
        )
    )
    # Explicit ":latest", not a bare tag — Ollama silently stores an
    # untagged pull as ":latest" anyway, so requesting it up front keeps
    # this string byte-identical to what a later /api/tags lookup returns.
    assert untrusted.ollama_name == "hf.co/org/Model-GGUF:latest"
    assert untrusted.fit is FitLevel.MARGINAL  # downgraded: quant not trustworthy


def test_no_gguf_sources_and_no_native_name_leaves_ollama_name_none() -> None:
    """Nothing to fall back to leaves ollama_name unset, fit untouched."""
    model = _parse_model(_row(ollama_name=None, gguf_sources=[]))
    assert model.ollama_name is None
    assert model.fit is FitLevel.PERFECT  # nothing to downgrade for


def test_fallback_helper_directly() -> None:
    """No sources -> None; only a trusted (llama_cpp) quant gets a tag."""
    assert _fallback_ollama_name((), "llama_cpp", "Q4_K_M") is None
    assert (
        _fallback_ollama_name(("org/repo",), "llama_cpp", "Q4_K_M")
        == "hf.co/org/repo:Q4_K_M"
    )
    assert (
        _fallback_ollama_name(("org/repo",), "mlx", "mlx-4bit")
        == "hf.co/org/repo:latest"
    )
    assert (
        _fallback_ollama_name(("org/repo",), "llama_cpp", None)
        == "hf.co/org/repo:latest"
    )


# --- persistent, fingerprinted cache ----------------------------------------


def _system_fixture() -> dict:
    return json.loads((FIXTURES / "system.json").read_text())


def _fit_fixture() -> dict:
    return json.loads((FIXTURES / "fit.json").read_text())


async def test_no_cache_file_scans_when_refresh_is_true(tmp_path: Path) -> None:
    """An explicit refresh scans and writes a cache even with none present yet."""
    cache_path = tmp_path / "cache.json"
    log = tmp_path / "calls.log"
    executable = _stub(tmp_path / "bin", _system_fixture(), _fit_fixture(), log=log)

    result = await LlmfitAdvisor(
        executable, "1.1.11", 2, cache_path=cache_path
    ).scan(8192, refresh=True)

    assert result.scanned is True
    assert len(result.models) == 2
    assert "fit" in log.read_text()
    assert cache_path.exists()


async def test_refresh_false_never_scans_without_a_cache(tmp_path: Path) -> None:
    """The expensive subprocess only ever runs on an explicit refresh."""
    cache_path = tmp_path / "cache.json"
    log = tmp_path / "calls.log"
    executable = _stub(tmp_path / "bin", _system_fixture(), _fit_fixture(), log=log)

    result = await LlmfitAdvisor(
        executable, "1.1.11", 2, cache_path=cache_path
    ).scan(8192, refresh=False)

    assert result.scanned is False
    assert result.models == ()
    assert "fit" not in log.read_text()
    assert not cache_path.exists()


async def test_cache_hit_skips_the_expensive_call(tmp_path: Path) -> None:
    """A fingerprint-matched cache answers without invoking the real binary."""
    cache_path = tmp_path / "cache.json"
    executable = _stub(tmp_path / "bin", _system_fixture(), _fit_fixture())
    advisor = LlmfitAdvisor(executable, "1.1.11", 2, cache_path=cache_path)
    await advisor.scan(8192, refresh=True)

    log = tmp_path / "calls.log"
    warm_executable = _stub(
        tmp_path / "bin2", _system_fixture(), _fit_fixture(), log=log
    )
    warm = LlmfitAdvisor(warm_executable, "1.1.11", 2, cache_path=cache_path)

    result = await warm.scan(8192, refresh=False)

    assert result.scanned is True
    assert len(result.models) == 2
    assert "fit" not in log.read_text()


async def test_fingerprint_mismatch_is_a_miss_not_an_error(tmp_path: Path) -> None:
    """A hardware/context change invalidates the cache instead of erroring."""
    cache_path = tmp_path / "cache.json"
    executable = _stub(tmp_path / "bin", _system_fixture(), _fit_fixture())
    await LlmfitAdvisor(executable, "1.1.11", 2, cache_path=cache_path).scan(
        8192, refresh=True
    )

    # A different max_context changes the fingerprint.
    result = await LlmfitAdvisor(
        executable, "1.1.11", 2, cache_path=cache_path
    ).scan(4096, refresh=False)

    assert result.scanned is False
    assert result.models == ()


async def test_corrupt_cache_file_is_discarded_silently(tmp_path: Path) -> None:
    """A corrupt cache file is treated as a miss, never raises."""
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{not-json")
    executable = _stub(tmp_path / "bin", _system_fixture(), _fit_fixture())

    result = await LlmfitAdvisor(
        executable, "1.1.11", 2, cache_path=cache_path
    ).scan(8192, refresh=False)

    assert result.scanned is False
    assert result.models == ()


async def test_wrong_cache_version_is_discarded(tmp_path: Path) -> None:
    """A cache written by an older schema is discarded, not misread."""
    cache_path = tmp_path / "cache.json"
    executable = _stub(tmp_path / "bin", _system_fixture(), _fit_fixture())
    await LlmfitAdvisor(executable, "1.1.11", 2, cache_path=cache_path).scan(
        8192, refresh=True
    )
    document = json.loads(cache_path.read_text())
    document["cache_version"] = CACHE_VERSION + 1
    cache_path.write_text(json.dumps(document))

    result = await LlmfitAdvisor(
        executable, "1.1.11", 2, cache_path=cache_path
    ).scan(8192, refresh=False)

    assert result.scanned is False
    assert result.models == ()


async def test_refresh_true_always_rescans_and_overwrites_cache(
    tmp_path: Path,
) -> None:
    """refresh=True re-scans even when a valid cache already exists."""
    cache_path = tmp_path / "cache.json"
    executable = _stub(tmp_path / "bin", _system_fixture(), _fit_fixture())
    advisor = LlmfitAdvisor(executable, "1.1.11", 2, cache_path=cache_path)
    await advisor.scan(8192, refresh=True)

    log = tmp_path / "calls.log"
    logged_executable = _stub(
        tmp_path / "bin2", _system_fixture(), _fit_fixture(), log=log
    )
    result = await LlmfitAdvisor(
        logged_executable, "1.1.11", 2, cache_path=cache_path
    ).scan(8192, refresh=True)

    assert result.scanned is True
    # A valid cache already existed, but refresh=True re-ran the expensive
    # call anyway rather than trusting it.
    assert "fit" in log.read_text()
