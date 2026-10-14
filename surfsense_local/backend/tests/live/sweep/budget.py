"""The sweep's hard cap: what is spent, what runs may still spend, and each run's own stop.

Each attempt keeps its own ledger, and the proxy refuses a call once that
ledger would pass the run's SURFSENSE_LIVE_STOP_DOLLARS. A run's stop is the
per-case cap, which stops a runaway model, or what is left of the sweep when
that is less. A case starts only while what is spent, plus what the runs in
flight are expected to cost, plus its own expected cost fits under the cap.
"""

from dataclasses import dataclass

from tests.live.sweep.model_list import ListedModel

# Input and output tokens of one run, about twice what the ladder's passing
# runs used: Sonnet's PDF brief was $0.34 and its board pack $0.48 at $2/$10.
CASE_TOKENS = {
    "smoke": (40_000, 2_000),
    "pdf-brief": (250_000, 12_000),
    "board-pack": (300_000, 12_000),
}


def estimate(model: ListedModel, case: str) -> float:
    """What one run of the case is expected to cost at the model's listed prices."""
    prompt, completion = CASE_TOKENS[case]
    return (prompt * model.prompt + completion * model.completion) / 1_000_000


@dataclass(frozen=True)
class Budget:
    cap: float
    case_cap: float

    def room(self, spent: float, in_flight: list[float]) -> float:
        return self.cap - spent - sum(in_flight)

    def may_start(self, spent: float, in_flight: list[float], expected: float) -> bool:
        return self.room(spent, in_flight) >= expected

    def stop_for(self, spent: float, in_flight: list[float]) -> tuple[float, bool]:
        """The run's stop, and whether it is the per-case cap rather than the sweep's last dollars."""
        room = self.room(spent, in_flight)
        if room >= self.case_cap:
            return self.case_cap, True
        return max(0.0, room), False
