"""A run cancelled while its runner works: raised by every runner, caught by the Studio worker."""


class FillStoppedError(Exception):
    """The run was cancelled between questions."""
