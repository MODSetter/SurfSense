"""The run-level question: what the verdicts say to change first."""

import json
from pathlib import Path

from modules.llm.providers.types import Message

_PROMPT = Path(__file__).with_name("report.md").read_text(encoding="utf-8")
# Chat's system message is the instructions, then the grounding from here on.
_GROUNDING = "\n\n<retrieved_context>"


def report_request(results: list[dict], verdicts: list[dict]) -> list[Message]:
    """Every verdict beside its answer and rule checks, and the model's instructions."""
    first = results[0]
    instructions = first["messages"][0]["content"].split(_GROUNDING)[0]
    replies = {(r["case"], r["repeat"]): r for r in results}
    lines = []
    for verdict in verdicts:
        reply = replies[verdict["case"], verdict["repeat"]]
        entry = {
            "case": verdict["case"],
            "repeat": verdict["repeat"],
            "question": reply["messages"][-1]["content"],
            "answer": reply["answer"],
            "checks": reply["score"],
            "verdict": verdict.get("verdict") or {"error": verdict["error"]},
        }
        lines.append(json.dumps(entry, ensure_ascii=False))
    judged = "\n".join(lines)
    return [
        Message("system", _PROMPT),
        Message(
            "user",
            f"Model: {first['model']}, on the {first['tier']} prompt tier\n\n"
            f"<instructions>\n{instructions}\n</instructions>\n\n"
            f"<verdicts>\n{judged}\n</verdicts>",
        ),
    ]
