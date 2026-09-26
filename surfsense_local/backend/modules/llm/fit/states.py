"""Where a model's weights will live, which is the only thing a badge claims."""

from enum import StrEnum


class FitState(StrEnum):
    FITS = "fits"
    PARTIAL = "partial"
    TOO_BIG = "too_big"
