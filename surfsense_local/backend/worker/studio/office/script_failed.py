"""A Studio script that failed, and how much of the failure the model is shown."""

# What of a failure the model is shown to fix it: the error and the traceback's end.
REPAIR_CHARS = 2000


class StudioScriptFailedError(RuntimeError):
    """Studio's script failed; Retry asks the model again, so no "Script error:" mark."""

    def __init__(self, error: str, shown: str | None = None) -> None:
        super().__init__(f"The document script failed: {error}")
        # The error and the traceback's end, as the model is shown them to fix it.
        self.shown = shown or error
