"""Whether this install keeps usage statistics at all: never the Docker image (ADR 0075)."""

from api.config import get_settings


def usage_statistics_kept() -> bool:
    # Nothing in the image reports them, so nothing is counted or served to report.
    return not get_settings().in_container()
