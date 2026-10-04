"""What one live run leaves for the maintainer: the transcript, every document version, its previews and its cost.

Written to references/live-runs/<UTC timestamp>-<case>/, which git ignores.
"""

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.live.spend_ledger import LIVE_RUNS, SpendLedger, Usage

# A step that read a whole file would bury the turn; the full calls are in model-requests.json.
_SHOWN_OUTPUT_CHARS = 2500


class RunFolder:
    def __init__(self, case: str, root: Path = LIVE_RUNS) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.case = case
        self.path = root / f"{stamp}-{case}"
        self.path.mkdir(parents=True)
        self.turns: list[dict[str, Any]] = []

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
                    **usage.__dict__,
                    "dollars": round(usage.dollars, 4),
                    "model_requests": len(exchanges),
                    # Cut off before Anthropic said what they used: charged at the worst case.
                    "estimated_model_requests": sum(
                        1 for e in exchanges if e["usage_estimated"]
                    ),
                    "ledger_dollars_after": round(ledger.total().dollars, 4),
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
                        "outcome": outcome,
                        "detail": detail,
                        "word_previews": word_previews,
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
        lines += ["", "```python", script, "```"]
    result = step.get("output") or step.get("error") or ""
    if len(result) > _SHOWN_OUTPUT_CHARS:
        result = result[:_SHOWN_OUTPUT_CHARS] + "\n… (cut here)"
    if step.get("artifact"):
        lines += ["", f"Made: `{json.dumps(step['artifact'])}`"]
    return [*lines, "", "Result:", "", "```text", result, "```", ""]


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", name)
