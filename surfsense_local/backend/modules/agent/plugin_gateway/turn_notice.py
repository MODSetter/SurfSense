"""A plugin named in the thread's running turn, mid-reply, beside those named at its start."""

import json

from starlette.requests import Request


def tell_turn(request: Request, thread_id: int, title: str, reason: str) -> None:
    """Nothing when the thread is not answering: its plugin's status says the same."""
    run = request.app.state.chat_runs.get(thread_id)
    if run is None:
        return
    notice = {
        "type": "agent-plugins-unavailable",
        "plugins": [{"title": title, "reason": reason}],
    }
    run.add(f"data: {json.dumps(notice)}\n\n".encode())
