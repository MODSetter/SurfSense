"""What the remote catalog routes return."""

from pydantic import BaseModel, ConfigDict

from modules.llm.catalog.remote.catalog import ProviderSummary
from modules.llm.catalog.remote.manifest.schema import Connect
from modules.llm.catalog.remote.rows import Availability, RemoteRow
from modules.llm.catalog.source import Source
from modules.llm.model_type import ModelType

__all__ = ["RemoteProviderRead", "RemoteRowRead"]


def _ordered(types: frozenset[ModelType] | tuple[ModelType, ...]) -> list[ModelType]:
    """Enum order, so a row's types read the same wherever they are shown."""
    return [model_type for model_type in ModelType if model_type in types]


class RemoteProviderRead(BaseModel):
    id: str
    name: str
    doc: str | None
    connect: Connect
    type_counts: dict[ModelType, int]
    connections: int

    @classmethod
    def of(cls, summary: ProviderSummary) -> "RemoteProviderRead":
        return cls(
            id=summary.id,
            name=summary.name,
            doc=summary.doc,
            connect=summary.connect,
            type_counts=summary.type_counts,
            connections=summary.connections,
        )


class ConnectionRefRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str


class SupportsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool_call: bool | None
    reasoning: bool | None
    structured_output: bool | None
    context_window: int | None


class RemoteRowRead(BaseModel):
    source: Source
    provider: str
    connection: ConnectionRefRead | None
    model_id: str
    name: str
    types: list[ModelType]
    known: bool
    selectable_for: list[ModelType]
    supports: SupportsRead | None
    status: str | None
    availability: Availability
    reason: str | None

    @classmethod
    def of(cls, row: RemoteRow) -> "RemoteRowRead":
        return cls(
            source=row.source,
            provider=row.provider,
            connection=ConnectionRefRead.model_validate(row.connection)
            if row.connection
            else None,
            model_id=row.model_id,
            name=row.name,
            types=_ordered(row.types),
            known=row.known,
            selectable_for=_ordered(row.selectable_for),
            supports=SupportsRead.model_validate(row.supports) if row.supports else None,
            status=row.status,
            availability=row.availability,
            reason=row.reason,
        )
