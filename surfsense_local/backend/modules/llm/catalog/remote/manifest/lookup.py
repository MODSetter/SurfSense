"""Which manifest entry describes a model a connection lists, and what it is.

A connection to a known provider reads that provider's entry. Anything else is
read across providers: the maker's own entry when the id names one, otherwise
the types every provider carrying the id agrees on. Each step tries the full id
and then its last path segment, since Gemini answers `models/<id>` and gateways
prefix a vendor. An id nothing carries is unknown, never guessed.
"""

from collections import defaultdict
from dataclasses import dataclass, fields
from typing import Literal

from modules.llm.catalog.remote.classifier import classify
from modules.llm.catalog.remote.manifest.schema import Call, RemoteManifest, RemoteModel
from modules.llm.catalog.remote.support import Supports, supports
from modules.llm.model_type import ModelType

__all__ = ["CallRoute", "RemoteClassification", "RemoteLookup"]

CallRoute = Literal["chat_completions", "responses"]


@dataclass(frozen=True)
class RemoteClassification:
    types: frozenset[ModelType]
    # False only when no entry describes the id; an empty `types` can be known.
    known: bool
    supports: Supports | None


UNKNOWN = RemoteClassification(types=frozenset(), known=False, supports=None)


class RemoteLookup:
    def __init__(self, manifest: RemoteManifest) -> None:
        self._manifest = manifest
        self._carriers: dict[str, list[RemoteModel]] = defaultdict(list)
        for provider in manifest.providers.values():
            for model_id, model in provider.models.items():
                self._carriers[model_id].append(model)

    @property
    def manifest(self) -> RemoteManifest:
        return self._manifest

    def has_provider(self, provider: str) -> bool:
        return provider in self._manifest.providers

    def classify(
        self, model_id: str, provider: str | None = None
    ) -> RemoteClassification:
        candidates = _candidates(model_id)
        served = self._manifest.providers.get(provider) if provider else None
        if served is not None:
            for candidate in candidates:
                if candidate in served.models:
                    return _one(candidate, served.models[candidate])
        return self._maker(model_id) or self._agreed(candidates) or UNKNOWN

    def unusable_reason(self, model_id: str, provider: str | None) -> str | None:
        """Why a model the manifest knows cannot be called here, or None.

        Only the provider a connection names is consulted: what some other
        provider cannot call says nothing about a custom endpoint, and a model
        no entry describes is unknown, not unusable.
        """
        served = self._manifest.providers.get(provider) if provider else None
        if served is None:
            return None
        for candidate in _candidates(model_id):
            model = served.models.get(candidate)
            if model is not None:
                if served.connect.status == "unreachable":
                    return served.connect.reason
                return call_reason(model.call)
        return None

    def call_route(self, model_id: str, provider: str | None) -> CallRoute:
        """The route a text model answers on: /responses where the provider a
        connection names records it, /chat/completions otherwise."""
        served = self._manifest.providers.get(provider) if provider else None
        if served is not None:
            for candidate in _candidates(model_id):
                model = served.models.get(candidate)
                if model is not None and model.call and model.call.route == "responses":
                    return "responses"
        return "chat_completions"

    def _maker(self, model_id: str) -> RemoteClassification | None:
        maker, _, rest = model_id.partition("/")
        entries = self._manifest.providers.get(maker) if rest else None
        if entries is None:
            return None
        for candidate in (rest, model_id):
            if candidate in entries.models:
                return _one(candidate, entries.models[candidate])
        return None

    def _agreed(self, candidates: tuple[str, ...]) -> RemoteClassification | None:
        for candidate in candidates:
            carriers = self._carriers.get(candidate)
            if carriers:
                types = frozenset.intersection(
                    *(classify(candidate, model) for model in carriers)
                )
                return RemoteClassification(
                    types=types,
                    known=True,
                    supports=_agreed_supports([supports(m) for m in carriers]),
                )
        return None


def call_reason(call: Call | None) -> str | None:
    """Why a model's own `call` puts it out of reach, or None."""
    if call is None or call.protocol is None:
        return None
    return (
        f"Served through the {call.protocol} protocol, which SurfSense does not speak"
    )


def _candidates(model_id: str) -> tuple[str, ...]:
    last = model_id.rsplit("/", 1)[-1]
    return (model_id,) if last == model_id else (model_id, last)


def _one(model_id: str, model: RemoteModel) -> RemoteClassification:
    return RemoteClassification(
        types=classify(model_id, model), known=True, supports=supports(model)
    )


def _agreed_supports(each: list[Supports]) -> Supports:
    """A feature every carrier reports the same way; None where they differ."""
    values = {
        field.name: {getattr(item, field.name) for item in each}
        for field in fields(Supports)
    }
    return Supports(
        **{
            name: next(iter(seen)) if len(seen) == 1 else None
            for name, seen in values.items()
        }
    )
