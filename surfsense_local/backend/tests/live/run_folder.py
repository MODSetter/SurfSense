"""What one live run leaves for the maintainer: the transcript, every document version, its previews and its cost.

Written to <live runs>/<UTC timestamp>-<case>-<provider>-<model>/, by default under
references/live-runs/, which git ignores.
"""

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modules.agent.agent_threads.steps import MAX_INPUT_CHARS
from tests.live.live_model import LiveModel
from tests.live.live_runs_dir import live_runs_dir
from tests.live.spend_ledger import SpendLedger, Usage

# A step that read a whole file would bury the turn; the full calls are in model-requests.json.
_SHOWN_OUTPUT_CHARS = 2500


class RunFolder:
    def __init__(self, case: str, model: LiveModel, root: Path | None = None) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.case = case
        self.model = model
        name = f"{stamp}-{case}-{model.provider.name}-{model.name}"
        self.path = (root or live_runs_dir()) / _safe(name)
        self.path.mkdir(parents=True)
        self.turns: list[dict[str, Any]] = []
        # What the case grades without failing on it, kept in result.json.
        self.metrics: dict[str, Any] = {}

    def keep_source(self, name: str, data: bytes) -> None:
        """A source the run made, as it was uploaded."""
        folder = self.path / "sources"
        folder.mkdir(exist_ok=True)
        (folder / name).write_bytes(data)

    def keep_document(self, name: str, data: bytes | None, script: str | None) -> None:
        """A version the agent rendered, or tried to, and the script behind it."""
        folder = self.path / "documents"
        folder.mkdir(exist_ok=True)
        path = folder / _safe(name)
        if data is not None:
            path.write_bytes(data)
        if script is not None:
            path.with_suffix(path.suffix + ".py").write_text(script, encoding="utf-8")

    def keep_previews(self, previews: Path) -> None:
        """The page images the render tool drew for the agent to check."""
        if previews.is_dir():
            shutil.copytree(previews, self.path / "previews", dirs_exist_ok=True)

    def keep_analysis(self, analysis: Path) -> None:
        """The tables and charts each analysis run saved, by run."""
        if analysis.is_dir():
            shutil.copytree(analysis, self.path / "analysis", dirs_exist_ok=True)

    def add_turn(self, text: str, frames: list[dict[str, Any]]) -> None:
        self.turns.append({"user": text, "frames": frames})

    def finish(
        self,
        *,
        exchanges: list[dict[str, Any]],
        usage: Usage,
        ledger: SpendLedger,
        outcome: str,
        detail: str,
        redact,
        word_previews: dict[str, Any],
    ) -> None:
        """Write the transcript, the model calls, the cost and how the case ended."""
        self._write(
            "frames.json", redact(json.dumps(self.turns, indent=2, ensure_ascii=False))
        )
        self._write(
            "model-requests.json",
            redact(json.dumps(exchanges, indent=2, ensure_ascii=False)),
        )
        self._write("transcript.md", redact(self._transcript()))
        self._write(
            "cost.json",
            json.dumps(
                {
                    "model": self.model.name,
                    "provider": self.model.provider.name,
                    "prices_per_million": self.model.prices.per_million(),
                    **usage.__dict__,
                    "dollars": round(self.model.prices.dollars(usage), 4),
                    "model_requests": len(exchanges),
                    # Cut off before the provider said what they used: charged at the worst case.
                    "estimated_model_requests": sum(
                        1 for e in exchanges if e["usage_estimated"]
                    ),
                    "ledger_dollars_after": round(ledger.dollars(), 4),
                    # What OpenRouter says it billed. It routes each call to one of
                    # several providers, most dearer than the listed price charged above.
                    "reported_dollars": _reported_dollars(exchanges),
                },
                indent=2,
            ),
        )
        self._write(
            "result.json",
            redact(
                json.dumps(
                    {
                        "case": self.case,
                        "model": self.model.name,
                        "provider": self.model.provider.name,
                        # Whether the app declared image input, from the manifest's row.
                        "reads_images": self.model.reads_images,
                        "outcome": outcome,
                        "detail": detail,
                        "word_previews": word_previews,
                        "metrics": self.metrics,
                    },
                    indent=2,
                )
            ),
        )

    def _transcript(self) -> str:
        lines = [f"# Live run: {self.case}", ""]
        for number, turn in enumerate(self.turns, 1):
            lines += [f"## Turn {number}", "", f"**User:** {turn['user']}", ""]
            frames = turn["frames"]
            for step in _finished_steps(frames):
                lines += _step_lines(step)
            for error in (f for f in frames if f["type"] == "error"):
                lines += [f"**Error:** {error.get('message')}", ""]
            answer = "".join(f["text"] for f in frames if f["type"] == "delta")
            lines += ["**Agent:**", "", answer or "(no answer)", ""]
        return "\n".join(lines)

    def _write(self, name: str, text: str) -> None:
        (self.path / name).write_text(text, encoding="utf-8")


def _finished_steps(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each tool call's last state, in the order the calls started."""
    last: dict[str, dict[str, Any]] = {}
    for frame in frames:
        if frame["type"] == "agent-step":
            last[frame["id"]] = frame
    return list(last.values())


def _step_lines(step: dict[str, Any]) -> list[str]:
    arguments = dict(step.get("input") or {})
    script = arguments.pop("script", None)
    lines = [
        f"### `{step.get('tool')}` ({step.get('status')})",
        "",
        "```json",
        json.dumps(arguments, indent=2, ensure_ascii=False),
        "```",
    ]
    if script is not None:
        # Only a version's own .py holds the rest, and a refused render has none.
        if len(script) > MAX_INPUT_CHARS:
            lines += [
                "",
                f"The script's first {MAX_INPUT_CHARS} characters; "
                "the whole call is in model-requests.json:",
            ]
        lines += ["", "```python", script, "```"]
    result = step.get("output") or step.get("error") or ""
    if len(result) > _SHOWN_OUTPUT_CHARS:
        result = result[:_SHOWN_OUTPUT_CHARS] + "\n… (cut here)"
    if step.get("artifact"):
        lines += ["", f"Made: `{json.dumps(step['artifact'])}`"]
    return [*lines, "", "Result:", "", "```text", result, "```", ""]


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", name)


def _reported_dollars(exchanges: list[dict[str, Any]]) -> float | None:
    """The provider's own bill for the run, or None when a call carried none."""
    costs = [e.get("reported_cost") for e in exchanges]
    if not costs or any(c is None for c in costs):
        return None
    return round(sum(costs), 4)
