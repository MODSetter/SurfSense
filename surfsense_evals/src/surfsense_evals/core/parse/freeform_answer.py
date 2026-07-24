"""Extract free-form answers from open-ended LLM responses.

Used by benchmarks that don't have a fixed letter set (MMLongBench-Doc,
DocVQA-style benchmarks, future legal/finance suites). The contract:

* Strip leading "Answer:" / "Final answer:" markers if present.
* Drop fenced code blocks if the model wrapped its answer in one.
* Trim leading/trailing whitespace.
* Return the *last* meaningful chunk — models often think out loud
  before stating the answer.

If the message is empty or only contains a fence, return ``""``.
"""

from __future__ import annotations

import re

_ANSWER_PREFIX = re.compile(
    r"^\s*(?:final\s*answer|the\s+answer\s+is|answer)\s*[:=\-]\s*",
    re.IGNORECASE,
)
# Marker-only regex (no capture group) used to find every "Answer:"
# token position. We then slice from the LAST marker's end to the
# next newline ourselves — robust to multiple inline answers because
# we never let the engine greedy-capture across markers.
_ANSWER_MARKER = re.compile(
    r"(?:final\s*answer|the\s+answer\s+is|answer)\s*[:=\-]\s*",
    re.IGNORECASE,
)
_FENCED_BLOCK = re.compile(r"```[a-zA-Z0-9]*\s*([\s\S]*?)\s*```")


def extract_freeform_answer(text: str) -> str:
    """Pull the model's final answer out of a possibly-verbose response."""

    if not text or not text.strip():
        return ""

    # 1. Find the last line that starts with an Answer: marker. If
    #    nothing matches, walk back to the last non-empty line.
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    candidate = ""
    for ln in reversed(lines):
        if not ln.strip():
            continue
        if _ANSWER_PREFIX.search(ln):
            candidate = _ANSWER_PREFIX.sub("", ln, count=1).strip()
            break

    if not candidate:
        # 2. Inline match: find every "Answer:" marker position and
        # slice from the LAST marker's end to the next newline. Robust
        # to "preamble.Answer: 42" one-liners and multiple inline
        # markers (we always pick the final, freshest one).
        marker_matches = list(_ANSWER_MARKER.finditer(text))
        if marker_matches:
            last = marker_matches[-1]
            tail = text[last.end() :]
            nl = tail.find("\n")
            if nl >= 0:
                tail = tail[:nl]
            candidate = tail.strip()

    if not candidate:
        # 3. No "Answer:" marker — try fenced blocks.
        fences = _FENCED_BLOCK.findall(text)
        if fences:
            candidate = fences[-1].strip()
        else:
            # Last non-empty line as a fallback.
            for ln in reversed(lines):
                if ln.strip():
                    candidate = ln.strip()
                    break

    # 2. Strip wrapping quotes / parens / trailing punctuation that
    #    confuse the grader without changing meaning.
    candidate = candidate.strip().strip("`").strip()
    if candidate.startswith(('"', "'")) and candidate.endswith(('"', "'")):
        candidate = candidate[1:-1].strip()
    return candidate


__all__ = ["extract_freeform_answer"]
