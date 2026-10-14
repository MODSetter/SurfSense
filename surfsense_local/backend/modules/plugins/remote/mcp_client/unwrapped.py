"""The one error inside the exception groups the SDK's task groups raise."""


def unwrapped(error: BaseException) -> BaseException:
    """The first leaf of nested groups, or the error itself when it is no group."""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    return error
