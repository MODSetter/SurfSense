"""A best-effort step's failures, logged once each, so a broken meter never floods the log."""

import logging


class LoggedOnce:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._logged: set[str] = set()

    def failed(self, step: str) -> None:
        """Called in an `except` block; the first failure of `step` keeps its traceback."""
        if step in self._logged:
            return
        self._logged.add(step)
        self._logger.exception(
            "[usage] %s failed; calls go on, and its later failures are not logged",
            step,
        )
