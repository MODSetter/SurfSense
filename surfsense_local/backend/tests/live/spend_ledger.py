"""What the live runs have spent on Claude Sonnet, kept across runs so the budget holds.

The maintainer's budget for live runs is $50; every run stops short of $45.
"""

import json
import threading
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

MODEL = "claude-sonnet-5-5"
# Dollars per million tokens for MODEL.
PRICES = {
    "input_tokens": 2.00,
    "output_tokens": 10.00,
    "cache_read_tokens": 0.20,
    "cache_write_tokens": 2.50,
}
STOP_DOLLARS = 45.0
# references/live-runs/, which .gitignore keeps out of the repo.
LIVE_RUNS = Path(__file__).resolve().parents[4] / "references" / "live-runs"


@dataclass(frozen=True)
class Usage:
    """Tokens one or more model calls used, as the provider reported them."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def dollars(self) -> float:
        return sum(
            getattr(self, name) * price / 1_000_000 for name, price in PRICES.items()
        )

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            *(getattr(self, f.name) + getattr(other, f.name) for f in fields(Usage))
        )


class SpendLedger:
    """The ledger file: cumulative tokens and dollars, and each case's share."""

    def __init__(
        self, path: Path = LIVE_RUNS / "spend.json", stop_dollars: float = STOP_DOLLARS
    ) -> None:
        self.path = path
        self.stop_dollars = stop_dollars
        self._lock = threading.Lock()

    def total(self) -> Usage:
        stored = self._read()
        return Usage(**{f.name: stored.get(f.name, 0) for f in fields(Usage)})

    def has_room(self, worst_case_dollars: float) -> bool:
        """Whether a call costing at most this keeps the total under the stop."""
        return self.total().dollars + worst_case_dollars < self.stop_dollars

    def add(self, usage: Usage, case: str) -> None:
        """Record a call's usage at once, so a run that crashes still counts."""
        with self._lock:
            stored = self._read()
            total = self.total() + usage
            by_case = stored.get("by_case", {})
            spent = Usage(**by_case.get(case, {})) + usage
            by_case[case] = asdict(spent)
            self._write(
                {
                    "model": MODEL,
                    "prices_per_million": PRICES,
                    "stop_dollars": self.stop_dollars,
                    **asdict(total),
                    "dollars": round(total.dollars, 6),
                    "updated": datetime.now(UTC).isoformat(timespec="seconds"),
                    "by_case": by_case,
                }
            )

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        partial = self.path.with_name(f".{self.path.name}.partial")
        partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        partial.replace(self.path)
