"""A plugin's server failed or refused a request, in a sentence the user can read."""


class ServerError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status: int | None = None,
        reason: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        # A network error, 408, 429 or 5xx: the same request may succeed again.
        self.retryable = retryable
        # The HTTP status the server answered, when it answered at all.
        self.status = status
        # The `reason` a refusal's body gave, as SurfSense's plugin host words a license refusal.
        self.reason = reason
        # The scopes a `403 insufficient_scope` asked for; None for any other refusal.
        self.scopes = scopes
