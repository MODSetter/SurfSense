"""One install the API is running, waiting to run, or just finished."""

from dataclasses import dataclass, field

from modules.llm.model_type import ModelType

# The events a job ends on; every other one means it is still going.
TERMINAL = frozenset({"complete", "error", "cancelled"})


@dataclass
class InstallJob:
    id: str
    catalog_id: str
    # What the screens call it while it downloads.
    label: str
    # The slots its model can fill, so each section shows only its own.
    model_types: tuple[ModelType, ...]
    select: bool
    model_type: ModelType | None
    # The latest install-stream event, the same frames the stream always sent.
    event: dict = field(default_factory=dict)
    finished_at: float | None = None

    @property
    def finished(self) -> bool:
        return self.event.get("type") in TERMINAL
