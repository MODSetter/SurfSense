from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    """One Studio deliverable the app can produce."""

    key: str
    label: str
    # Visual formats have no local builder; they call a BYO OpenRouter model.
    requires_key: bool = False


# The whole Studio catalog. Kept dependency-free so the API validates and lists
# without importing the builder libraries; the worker's BUILDERS registry must
# carry a builder for every non-visual key (asserted in the worker unit test).
FORMATS: tuple[Format, ...] = (Format("summary", "Summary"),)

FORMATS_BY_KEY: dict[str, Format] = {fmt.key: fmt for fmt in FORMATS}
