"""Unit tests for ``surfsense_evals.core.ingest_settings``.

Covers:

* ``IngestSettings.merge`` honours operator overrides and falls back
  to per-benchmark defaults when the operator is silent.
* ``add_ingest_settings_args`` exposes the three flag pairs and
  argparse defaults of ``None`` correctly distinguish "not passed"
  from "explicitly false".
* ``settings_header_line`` / ``read_settings_header`` round-trip
  through a JSONL file.
* ``read_settings_header`` is fault-tolerant: missing files, missing
  header, malformed JSON.
* ``format_ingest_settings_md`` produces a stable Markdown bullet.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from surfsense_evals.core.ingest_settings import (
    PROCESSING_MODES,
    SETTINGS_HEADER_KEY,
    IngestSettings,
    add_ingest_settings_args,
    format_ingest_settings_md,
    is_settings_header,
    read_settings_header,
    settings_header_line,
)

# ---------------------------------------------------------------------------
# IngestSettings.merge
# ---------------------------------------------------------------------------


class TestMerge:
    def test_silent_operator_uses_defaults(self) -> None:
        defaults = IngestSettings(use_vision_llm=True, processing_mode="basic")
        merged = IngestSettings.merge(defaults, {})
        assert merged == defaults

    def test_explicit_false_overrides_default_true(self) -> None:
        defaults = IngestSettings(use_vision_llm=True)
        merged = IngestSettings.merge(
            defaults, {"use_vision_llm": False}
        )
        assert merged.use_vision_llm is False

    def test_explicit_true_overrides_default_false(self) -> None:
        defaults = IngestSettings(use_vision_llm=False)
        merged = IngestSettings.merge(
            defaults, {"use_vision_llm": True}
        )
        assert merged.use_vision_llm is True

    def test_none_means_silent(self) -> None:
        # Argparse with BooleanOptionalAction yields None when the
        # operator passed neither --use-vision-llm nor --no-vision-llm.
        defaults = IngestSettings(use_vision_llm=True)
        merged = IngestSettings.merge(
            defaults, {"use_vision_llm": None}
        )
        assert merged.use_vision_llm is True

    def test_processing_mode_override(self) -> None:
        defaults = IngestSettings(processing_mode="basic")
        merged = IngestSettings.merge(
            defaults, {"processing_mode": "premium"}
        )
        assert merged.processing_mode == "premium"

    def test_processing_mode_invalid_raises(self) -> None:
        defaults = IngestSettings(processing_mode="basic")
        with pytest.raises(ValueError, match="Invalid processing_mode"):
            IngestSettings.merge(defaults, {"processing_mode": "exotic"})

    def test_processing_mode_blank_falls_back(self) -> None:
        defaults = IngestSettings(processing_mode="basic")
        merged = IngestSettings.merge(defaults, {"processing_mode": ""})
        assert merged.processing_mode == "basic"

    def test_string_truthy_coerced(self) -> None:
        defaults = IngestSettings(use_vision_llm=False)
        merged = IngestSettings.merge(defaults, {"use_vision_llm": "yes"})
        assert merged.use_vision_llm is True

    def test_string_falsy_coerced(self) -> None:
        defaults = IngestSettings(use_vision_llm=True)
        merged = IngestSettings.merge(defaults, {"use_vision_llm": "false"})
        assert merged.use_vision_llm is False

    def test_other_keys_ignored(self) -> None:
        # Benchmarks pass the whole opts dict; merge must tolerate
        # unrelated keys without crashing.
        defaults = IngestSettings(use_vision_llm=True, processing_mode="basic")
        merged = IngestSettings.merge(
            defaults,
            {
                "use_vision_llm": False,
                "concurrency": 4,
                "task_filter": "all",
                "no_mentions": True,
            },
        )
        assert merged.use_vision_llm is False
        assert merged.processing_mode == "basic"

    def test_to_dict_round_trips(self) -> None:
        s = IngestSettings(use_vision_llm=True, processing_mode="premium")
        d = s.to_dict()
        assert d == {
            "use_vision_llm": True,
            "processing_mode": "premium",
            "use_vision_llm": False,
        }

    def test_render_label_format(self) -> None:
        s = IngestSettings(use_vision_llm=True, processing_mode="premium")
        assert s.render_label() == "vision=on, mode=premium, summarize=on"


# ---------------------------------------------------------------------------
# add_ingest_settings_args
# ---------------------------------------------------------------------------


class TestAddArgs:
    @pytest.fixture
    def parser(self) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser()
        add_ingest_settings_args(
            p,
            defaults=IngestSettings(
                use_vision_llm=False, processing_mode="basic"
            ),
        )
        return p

    def test_silent_invocation_yields_none(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args([])
        assert args.use_vision_llm is None
        assert args.processing_mode is None
        assert args.use_vision_llm is None

    def test_use_vision_llm_flag(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args(["--use-vision-llm"])
        assert args.use_vision_llm is True

    def test_no_vision_llm_flag(self, parser: argparse.ArgumentParser) -> None:
        args = parser.parse_args(["--no-vision-llm"])
        assert args.use_vision_llm is False

    def test_processing_mode_choices(self, parser: argparse.ArgumentParser) -> None:
        for mode in PROCESSING_MODES:
            args = parser.parse_args(["--processing-mode", mode])
            assert args.processing_mode == mode

    def test_processing_mode_rejects_unknown(
        self, parser: argparse.ArgumentParser
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args(["--processing-mode", "exotic"])

    def test_summarize_flag_pair(self, parser: argparse.ArgumentParser) -> None:
        on = parser.parse_args(["--should-summarize"])
        assert on.use_vision_llm is True
        off = parser.parse_args(["--no-summarize"])
        assert off.use_vision_llm is False

    def test_vision_flags_mutually_exclusive(
        self, parser: argparse.ArgumentParser
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args(["--use-vision-llm", "--no-vision-llm"])

    def test_full_pipeline(self, parser: argparse.ArgumentParser) -> None:
        # Operator passes flags + defaults are reasonable. Merge
        # should yield exactly what they asked for.
        args = parser.parse_args(
            ["--use-vision-llm", "--processing-mode", "premium"]
        )
        defaults = IngestSettings(
            use_vision_llm=False, processing_mode="basic"
        )
        merged = IngestSettings.merge(defaults, vars(args))
        assert merged == IngestSettings(
            use_vision_llm=True, processing_mode="premium"
        )


# ---------------------------------------------------------------------------
# Header round-trip + read_settings_header fault tolerance
# ---------------------------------------------------------------------------


class TestHeader:
    def test_header_line_round_trip(self, tmp_path: Path) -> None:
        s = IngestSettings(use_vision_llm=True, processing_mode="premium")
        path = tmp_path / "map.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            fh.write(settings_header_line(s) + "\n")
            fh.write(json.dumps({"case_id": "x", "document_id": 1}) + "\n")
        loaded = read_settings_header(path)
        assert loaded == s.to_dict()

    def test_is_settings_header_recognises(self) -> None:
        assert is_settings_header({SETTINGS_HEADER_KEY: {}})
        assert not is_settings_header({"case_id": "x"})

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert read_settings_header(tmp_path / "does_not_exist.jsonl") == {}

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert read_settings_header(path) == {}

    def test_no_header_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "legacy.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"case_id": "x", "document_id": 1}) + "\n")
            fh.write(json.dumps({"case_id": "y", "document_id": 2}) + "\n")
        assert read_settings_header(path) == {}

    def test_malformed_json_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.jsonl"
        path.write_text("not json\n", encoding="utf-8")
        assert read_settings_header(path) == {}

    def test_skips_blank_first_lines(self, tmp_path: Path) -> None:
        s = IngestSettings(use_vision_llm=True)
        path = tmp_path / "padded.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            fh.write("\n\n")
            fh.write(settings_header_line(s) + "\n")
        assert read_settings_header(path) == s.to_dict()


# ---------------------------------------------------------------------------
# format_ingest_settings_md
# ---------------------------------------------------------------------------


class TestFormatMd:
    def test_full_settings(self) -> None:
        out = format_ingest_settings_md(
            {"use_vision_llm": True, "processing_mode": "premium", "use_vision_llm": True}
        )
        assert "vision_llm=`on`" in out
        assert "processing_mode=`premium`" in out
        assert "summarize=`on`" in out

    def test_default_off(self) -> None:
        out = format_ingest_settings_md(
            {"use_vision_llm": False, "processing_mode": "basic", "use_vision_llm": False}
        )
        assert "vision_llm=`off`" in out
        assert "processing_mode=`basic`" in out
        assert "summarize=`off`" in out

    def test_missing_returns_re_ingest_hint(self) -> None:
        # Empty dict + None + non-mapping should all degrade gracefully.
        for raw in [None, {}, "not-a-mapping"]:
            assert "(not recorded" in format_ingest_settings_md(raw)
