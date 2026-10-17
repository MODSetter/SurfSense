"""Claude Code's own files for a thread's session, under `<config home>/projects/<project>/`.

SurfSense's copy is the thread, so Claude Code's transcript is deleted after each
turn: measured, a running Claude Code went on and a resumed one loaded SurfSense's
copy alone. Its `<session id>/` folder stays until the thread goes, since a later
turn may read a result saved there. `delete_session` is not used: it gives up when
the transcript is already gone, leaving that folder behind.
"""

import shutil

from modules.agent.engines.claude_code.saved_results import claude_home


def drop_transcript(session_id: str) -> None:
    """After a turn: the transcript Claude Code wrote, never its saved results."""
    for transcript in (claude_home() / "projects").glob(f"*/{session_id}.jsonl"):
        transcript.unlink(missing_ok=True)


def delete_session_files(session_id: str) -> None:
    """With the thread, or a session left for another account: the transcript and its folder."""
    drop_transcript(session_id)
    for folder in (claude_home() / "projects").glob(f"*/{session_id}"):
        shutil.rmtree(folder, ignore_errors=True)
