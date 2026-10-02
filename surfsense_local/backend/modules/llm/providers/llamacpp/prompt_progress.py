"""How this runtime is asked how far it has read the prompt.

Measured at b11050 in router mode: a streamed chat sent `return_progress`
answers, before its first token, with chunks whose `delta.content` is null and
that carry `prompt_progress` (`total`, `cache`, `processed`, `time_ms`), one
per 2,048-token batch. `processed` starts at `cache`, so a follow-up turn whose
prefix is cached reports almost nothing left. Without the field no such chunk
is sent, and nothing is sent while the model itself loads.
"""

PROMPT_PROGRESS: dict[str, object] = {"return_progress": True}
