"""A revised copy that will not be made, in a sentence the agent or the interface passes on."""


class RevisedCopyRefusedError(Exception):
    """Refused before any version exists, so nothing is left to clean up.

    A refusal the panel can meet carries a ``code`` and its ``values`` for the
    interface's own line (studio-error-text.ts); the agent passes the sentence on.
    """

    def __init__(
        self, message: str, code: str | None = None, **values: str | int
    ) -> None:
        super().__init__(message)
        self.code = code
        self.values = values
