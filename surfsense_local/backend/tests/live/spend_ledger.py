"""What the live runs have spent, in dollars across every model, kept across runs so the budget holds.

The first night's budget was $50, with runs stopping short of $45; a sweep sets
its own stop with SURFSENSE_LIVE_STOP_DOLLARS.
"""

import json
import os
import threading
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.live.live_runs_dir import live_runs_dir
from tests.live.model_prices import Prices
from tests.live.usage import Usage

__all__ = ["STOP_DOLLARS", "SpendLedger", "Usage"]

STOP_DOLLARS = 45.0


class SpendLedger:
    """The ledger file: dollars per model and per case, and their sum."""

    def __init__(
        self, path: Path | None = None, stop_dollars: float | None = None
    ) -> None:
        self.path = path or live_runs_dir() / "spend.json"
        if stop_dollars is None:
            stop_dollars = float(
                os.environ.get("SURFSENSE_LIVE_STOP_DOLLARS") or STOP_DOLLARS
            )
        self.stop_dollars = stop_dollars
        self._lock = threading.Lock()

    def dollars(self) -> float:
        return sum(entry["dollars"] for entry in self._read()["by_model"].values())

    def usage(self, model: str) -> Usage:
        """The tokens one model has used; tokens of different models never add."""
        return _tokens(self._read()["by_model"].get(model, {}))

    def has_room(self, worst_case_dollars: float) -> bool:
        """Whether a call costing at most this keeps the total under the stop."""
        return self.dollars() + worst_case_dollars < self.stop_dollars

    def add(self, usage: Usage, prices: Prices, *, case: str, model: str) -> None:
        """Record a call's usage at once, priced now, so a run that crashes still counts."""
        dollars = prices.dollars(usage)
        with self._lock:
            stored = self._read()
            entry = stored["by_model"].setdefault(model, {"by_case": {}})
            _charge(entry, usage, dollars)
            entry["prices_per_million"] = prices.per_million()
            _charge(entry["by_case"].setdefault(case, {}), usage, dollars)
            total = sum(e["dollars"] for e in stored["by_model"].values())
            self._write(
                {
                    "stop_dollars": self.stop_dollars,
                    "dollars": round(total, 6),
                    "updated": datetime.now(UTC).isoformat(timespec="seconds"),
                    "by_model": stored["by_model"],
                }
            )

    def _read(self) -> dict[str, Any]:
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"by_model": {}}
        return stored if "by_model" in stored else _from_first_night(stored)

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        partial = self.path.with_name(f".{self.path.name}.partial")
        partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        partial.replace(self.path)


def _charge(entry: dict[str, Any], usage: Usage, dollars: float) -> None:
    entry.update(asdict(_tokens(entry) + usage))
    entry["dollars"] = round(entry.get("dollars", 0) + dollars, 6)


def _tokens(entry: dict[str, Any]) -> Usage:
    return Usage(**{f.name: entry.get(f.name, 0) for f in fields(Usage)})


def _from_first_night(stored: dict[str, Any]) -> dict[str, Any]:
    """The shape before the ladder, one model on Anthropic: its total kept as written, its cases priced at its own rates."""
    if not stored:
        return {"by_model": {}}
    rates = stored["prices_per_million"]
    prices = Prices(
        input=rates["input_tokens"],
        output=rates["output_tokens"],
        cache_read=rates["cache_read_tokens"],
        cache_write=rates["cache_write_tokens"],
    )
    by_case = {
        case: {
            **asdict(_tokens(spent)),
            "dollars": round(prices.dollars(_tokens(spent)), 6),
        }
        for case, spent in stored.get("by_case", {}).items()
    }
    entry = {
        **asdict(_tokens(stored)),
        "dollars": stored["dollars"],
        "prices_per_million": rates,
        "by_case": by_case,
    }
    return {"by_model": {f"anthropic/{stored['model']}": entry}}
