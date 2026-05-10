"""Resolve which agent owns a streamed event from its LangGraph run lineage."""

from __future__ import annotations

from collections.abc import Iterable

from .emitter import Emitter, main_emitter


class EmitterRegistry:
    def __init__(self) -> None:
        self._by_run_id: dict[str, Emitter] = {}

    def register(self, run_id: str, emitter: Emitter) -> None:
        if not run_id:
            return
        self._by_run_id[run_id] = emitter

    def unregister(self, run_id: str) -> Emitter | None:
        if not run_id:
            return None
        return self._by_run_id.pop(run_id, None)

    def get(self, run_id: str | None) -> Emitter | None:
        if not run_id:
            return None
        return self._by_run_id.get(run_id)

    def resolve(
        self,
        *,
        run_id: str | None,
        parent_ids: Iterable[str] | None,
    ) -> Emitter:
        own = self.get(run_id)
        if own is not None:
            return own
        if parent_ids:
            for ancestor in reversed(list(parent_ids)):
                emitter = self.get(ancestor)
                if emitter is not None:
                    return emitter
        return main_emitter()

    def has_active_subagents(self) -> bool:
        return any(emitter.level == "subagent" for emitter in self._by_run_id.values())

    def clear(self) -> None:
        self._by_run_id.clear()
