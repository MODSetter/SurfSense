"""Identity of a cacheable parse: equal keys yield identical markdown."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParseKey:
    source_sha256: str
    etl_service: str
    mode: str
    version: int

    @classmethod
    def for_document(
        cls, source_sha256: str, *, etl_service: str, mode: str, version: int
    ) -> "ParseKey":
        return cls(
            source_sha256=source_sha256,
            etl_service=etl_service,
            mode=mode,
            version=version,
        )

    @property
    def object_suffix(self) -> str:
        return f"{self.etl_service}.{self.mode}.v{self.version}.md"
