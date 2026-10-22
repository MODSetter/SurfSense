"""An SRT track as plain lines: no cue numbers, no timings, no caption repeated."""

import re

_TIMING = re.compile(r"^\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+")


def transcript(srt: str) -> str:
    lines: list[str] = []
    for line in srt.splitlines():
        line = line.strip()
        if not line or line.isdigit() or _TIMING.match(line):
            continue
        # Auto-generated tracks roll each caption into the next cue.
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return "\n".join(lines)
