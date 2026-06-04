"""Per-upload ingestion settings shared across every benchmark.

The SurfSense ``POST /api/v1/documents/fileupload`` endpoint exposes
exactly three knobs (verified at
``surfsense_backend/app/routes/documents_routes.py`` and
``surfsense_backend/app/etl_pipeline/etl_document.py``):

* ``processing_mode``     — ``"basic"`` (default) | ``"premium"``
* ``use_vision_llm``      — ``bool`` (run vision LLM during ingest to
                            extract image content / captions / tables)

This module gives every benchmark a uniform way to:

1. Receive sensible per-benchmark defaults (text-only benchmarks
   default vision off; image-bearing benchmarks default vision on).
2. Accept CLI overrides (``--use-vision-llm`` / ``--no-vision-llm``,
   ``--processing-mode {basic,premium}``).
3. Persist the *actual* settings used into the doc-map manifest and
   the run artifact so reports can show "vision=ON, mode=premium →
   65% accuracy" head-to-head with "vision=OFF, mode=basic → 52%".

A/B testing on the same corpus
------------------------------

SurfSense dedupes uploads by ``(filename, search_space_id)`` — NOT by
content hash and NOT by ingestion settings. Re-uploading the same
filename to the same SearchSpace with a different ``use_vision_llm``
flag will hit the duplicate branch and *not* re-process. To compare
two settings combos head-to-head on the same corpus you must give
each combo its own SearchSpace, which today means:

    teardown --suite <s>
    setup    --suite <s> ...
    ingest   <s> <bench>  --no-vision-llm   # baseline run
    run      <s> <bench>
    teardown --suite <s>
    setup    --suite <s> ...
    ingest   <s> <bench>  --use-vision-llm  # vision arm
    run      <s> <bench>

The runs land in different timestamped subdirectories under
``data/<suite>/runs/`` and ``report --suite <s>`` aggregates whichever
manifest is currently latest per benchmark.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Keep the constant list of valid processing modes here so benchmarks
# don't have to re-import from the backend (they don't have access to
# the backend package anyway).
PROCESSING_MODES: tuple[str, ...] = ("basic", "premium")


@dataclass(frozen=True)
class IngestSettings:
    """Resolved per-upload knobs handed to ``DocumentsClient.upload``.

    Use ``IngestSettings(...)`` directly to define benchmark defaults,
    or ``IngestSettings.merge(defaults, opts)`` to apply CLI overrides
    on top of those defaults.
    """

    use_vision_llm: bool = False
    processing_mode: str = "basic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "use_vision_llm": self.use_vision_llm,
            "processing_mode": self.processing_mode,
        }

    @classmethod
    def merge(cls, defaults: IngestSettings, opts: Mapping[str, Any]) -> IngestSettings:
        """Apply CLI overrides on top of ``defaults``.

        ``opts`` is the kwargs dict built by ``core.cli`` from the
        argparse namespace (see ``_cmd_ingest`` / ``_cmd_run``). Keys
        we look for: ``use_vision_llm`` (bool or None), ``processing_mode``
        (str or None). Anything
        else is ignored so benchmarks can pass through their own opts.
        """

        return cls(
            use_vision_llm=_coerce_bool(opts.get("use_vision_llm"), defaults.use_vision_llm),
            processing_mode=_coerce_mode(opts.get("processing_mode"), defaults.processing_mode),
        )

    def render_label(self) -> str:
        """Human-readable single-line label for reports / log lines."""

        return (
            f"vision={'on' if self.use_vision_llm else 'off'}, "
            f"mode={self.processing_mode}"
        )


def _coerce_bool(value: Any, default: bool) -> bool:
    """Argparse with ``BooleanOptionalAction`` yields True/False/None.

    ``None`` means the operator didn't pass the flag → fall back to
    the benchmark default.
    """

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_mode(value: Any, default: str) -> str:
    if value is None or value == "":
        return default
    val = str(value).strip().lower()
    if val not in PROCESSING_MODES:
        raise ValueError(
            f"Invalid processing_mode {val!r}; must be one of {PROCESSING_MODES}"
        )
    return val


# ---------------------------------------------------------------------------
# Argparse helper
# ---------------------------------------------------------------------------


def _add_bool_pair(
    parser: argparse.ArgumentParser,
    *,
    dest: str,
    on_flag: str,
    off_flag: str,
    on_help: str,
    off_help: str,
) -> None:
    """Add a mutually exclusive ``--foo`` / ``--no-foo`` pair.

    We don't use ``argparse.BooleanOptionalAction`` because it would
    auto-generate ``--no-use-vision-llm`` rather than the friendlier
    ``--no-vision-llm`` that operators reach for. Default is ``None``
    so ``IngestSettings.merge`` can distinguish "silent" from
    "explicit false".
    """

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        on_flag,
        dest=dest,
        action="store_true",
        default=None,
        help=on_help,
    )
    group.add_argument(
        off_flag,
        dest=dest,
        action="store_false",
        default=None,
        help=off_help,
    )


def add_ingest_settings_args(
    parser: argparse.ArgumentParser,
    *,
    defaults: IngestSettings,
) -> None:
    """Attach ingest-settings flags to ``parser``.

    The vision bool exposes a mutually exclusive ``--foo`` / ``--no-foo``
    pair so an operator can flip either direction without restating every
    flag. Default is ``None`` so that "operator didn't pass the flag" is
    distinguishable from "operator explicitly passed false" —
    ``IngestSettings.merge`` then folds in the benchmark default only when
    the operator was silent.
    """

    settings_group = parser.add_argument_group(
        "ingest settings",
        f"Per-upload knobs (forwarded to /documents/fileupload). "
        f"Defaults for this benchmark: {defaults.render_label()}.",
    )
    _add_bool_pair(
        settings_group,
        dest="use_vision_llm",
        on_flag="--use-vision-llm",
        off_flag="--no-vision-llm",
        on_help=(
            "Run vision LLM during ingest to extract image content "
            f"(default for this benchmark: "
            f"{'on' if defaults.use_vision_llm else 'off'})."
        ),
        off_help="Skip vision LLM during ingest (text-only ETL).",
    )
    settings_group.add_argument(
        "--processing-mode",
        dest="processing_mode",
        choices=PROCESSING_MODES,
        default=None,
        help=(
            "SurfSense ETL processing mode (premium uses a 10x page "
            f"multiplier and typically routes to a stronger ETL). "
            f"Default for this benchmark: {defaults.processing_mode!r}."
        ),
    )


# ---------------------------------------------------------------------------
# Doc-map manifest helpers
# ---------------------------------------------------------------------------
#
# Every benchmark writes a doc-map JSONL under ``data/<suite>/maps/`` that
# pairs source identifiers (case_id, snippet_id, doc_path, …) to the
# SurfSense document_ids returned by the upload. To make the report
# self-describing we also write a header line:
#
#     {"__settings__": {"use_vision_llm": ..., "processing_mode": ..., ...}}
#
# These two helpers centralise that protocol so each benchmark only has to
# call ``write_settings_header`` and ``read_settings_header``.

SETTINGS_HEADER_KEY = "__settings__"


def settings_header_line(settings: IngestSettings) -> str:
    """Return the JSON-serialised header line (no trailing newline)."""

    return json.dumps({SETTINGS_HEADER_KEY: settings.to_dict()})


def is_settings_header(row: Mapping[str, Any]) -> bool:
    return SETTINGS_HEADER_KEY in row


def read_settings_header(map_path: Path) -> dict[str, Any]:
    """Read the ``__settings__`` header out of a doc-map JSONL.

    Returns ``{}`` on a missing file, an empty file, an unreadable
    file, or a file whose first non-blank line is not a settings
    header (e.g. a corpus ingested before this feature existed).
    Callers use this purely to surface settings in the report; it
    must never fail the run.
    """

    if not map_path.exists():
        return {}
    try:
        with map_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if isinstance(row, dict) and SETTINGS_HEADER_KEY in row:
                    return dict(row[SETTINGS_HEADER_KEY])
                return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def format_ingest_settings_md(settings: Any) -> str:
    """Render the resolved settings as a single Markdown bullet line."""

    if not isinstance(settings, Mapping) or not settings:
        return "- SurfSense ingest settings: (not recorded — re-ingest to capture)"
    vision = "on" if settings.get("use_vision_llm") else "off"
    mode = settings.get("processing_mode") or "basic"
    return (
        f"- SurfSense ingest settings: vision_llm=`{vision}`, "
        f"processing_mode=`{mode}`"
    )


__all__ = [
    "PROCESSING_MODES",
    "SETTINGS_HEADER_KEY",
    "IngestSettings",
    "add_ingest_settings_args",
    "format_ingest_settings_md",
    "is_settings_header",
    "read_settings_header",
    "settings_header_line",
]
