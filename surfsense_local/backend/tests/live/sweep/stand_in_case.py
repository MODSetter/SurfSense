"""A stand-in for one live case, for the runner's tests: it leaves the run folder a real case would, as a plan says.

usage: python stand_in_case.py <case>, with STAND_IN_PLAN naming a JSON file of
{"<model>|<case>": ["passed", "failed", "transient", "harness", "chat",
"hang", "hang-silent"]}, one entry per attempt. Each run charges
STAND_IN_DOLLARS (default $0.10) to its own ledger.
"""

import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    """Play the planned outcome for this attempt."""
    case = sys.argv[1]
    runs = Path(os.environ["SURFSENSE_LIVE_RUNS_DIR"])
    model = os.environ["SURFSENSE_LIVE_MODEL"]
    plan = json.loads(Path(os.environ["STAND_IN_PLAN"]).read_text(encoding="utf-8"))
    attempt = int(runs.name)
    planned = plan.get(f"{model}|{case}", ["passed"] * 9)
    outcome = planned[min(attempt, len(planned)) - 1]
    # One file per run: parallel lanes appending to one file can lose lines on Windows.
    trace = Path(os.environ["STAND_IN_TRACE"])
    trace.mkdir(parents=True, exist_ok=True)
    (trace / f"{os.getpid()}-{time.time_ns()}.json").write_text(
        json.dumps(
            {
                "model": model,
                "case": case,
                "attempt": attempt,
                "start": time.time(),
                "port_base": os.environ.get("SURFSENSE_LIVE_PORT_BASE"),
                "data_dir": os.environ.get("SURFSENSE_LOCAL_DATA_DIR"),
                "temp": os.environ.get("TEMP"),
                "stop": os.environ.get("SURFSENSE_LIVE_STOP_DOLLARS"),
                "provider": os.environ.get("SURFSENSE_LIVE_PROVIDER"),
            }
        ),
        encoding="utf-8",
    )
    dollars = float(os.environ.get("STAND_IN_DOLLARS", "0.1"))
    wrote = 0 if outcome == "hang-silent" else 500
    (runs / "spend.json").write_text(
        json.dumps({"dollars": dollars, "by_model": {model: {"output_tokens": wrote}}}),
        encoding="utf-8",
    )
    if outcome.startswith("hang"):
        time.sleep(60)
        return 0
    time.sleep(float(os.environ.get("STAND_IN_SECONDS", "0.2")))
    if outcome == "harness":
        return 2
    if outcome == "chat":
        (runs / "pytest.log").write_text(
            "WARNING thread 1 opens as a chat: the agent is not ready\n",
            encoding="utf-8",
        )
    folder = runs / f"20261007T000000Z-{case}-stand-in"
    folder.mkdir(parents=True)
    exchanges = [{"status": 200, "error": None, "served_by": "Upstream"}]
    frames = [{"user": "go", "frames": [{"type": "completed", "text": "done"}]}]
    if outcome == "transient":
        exchanges.append({"status": 503, "error": '{"code": 503}'})
        frames[0]["frames"] = [{"type": "error", "message": "upstream"}]
    failed = outcome != "passed"
    result = {
        "case": case,
        "model": model,
        "outcome": "failed" if failed else "passed",
        "detail": f"E   AssertionError: {case} planned to fail" if failed else "",
        "word_previews": {},
    }
    for name, data in (
        ("result.json", result),
        ("model-requests.json", exchanges),
        ("frames.json", frames),
        ("cost.json", {"dollars": dollars, "reported_dollars": dollars}),
    ):
        (folder / name).write_text(json.dumps(data), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
