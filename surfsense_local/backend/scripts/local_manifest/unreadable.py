"""The one refusal every engine's assembly raises."""


class UnreadableBuildError(Exception):
    """A build or file this refresh could not read completely. Nothing unknown is
    written, so nothing unknown can be recommended."""
