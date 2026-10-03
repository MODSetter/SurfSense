class SignInRequiredError(Exception):
    """The account's tokens are gone or refused; only signing in again fixes it."""

    def __init__(
        self, message: str = "the ChatGPT account has to sign in again"
    ) -> None:
        super().__init__(message)


class PlanLimitError(Exception):
    """The plan's usage limit is reached. Retrying before it resets cannot help."""
