"""Small manifests, built in a line, for the remote catalog's pure functions."""

from collections.abc import Callable

import pytest

from modules.llm.catalog.remote.manifest.lookup import RemoteLookup
from modules.llm.catalog.remote.manifest.schema import RemoteManifest

CHAT = {"input": ["text"], "output": ["text"]}
PAINTER = {"input": ["text"], "output": ["image"]}


def connect(status: str = "ready", reason: str | None = None) -> dict:
    """A provider's `connect` block; ready unless told otherwise."""
    return {
        "status": status,
        "base_url": "https://api.example.com/v1" if status == "ready" else None,
        "base_url_origin": "models.dev" if status == "ready" else None,
        "account_fields": [],
        "key": "required",
        "local": False,
        "reason": reason,
    }


def model(modalities: dict = CHAT, **fields: object) -> dict:
    """A manifest model entry; a chat model unless told otherwise."""
    return {
        "name": "Model",
        "family": None,
        "description": None,
        "release_date": None,
        "status": None,
        "modalities": modalities,
        "context": 128000,
        "output_limit": None,
        "tool_call": True,
        "reasoning": False,
        "reasoning_options": None,
        "structured_output": None,
        "temperature": None,
        "call": None,
        **fields,
    }


@pytest.fixture
def lookup_of() -> Callable[[dict], RemoteLookup]:
    """{provider: {"connect": ..., "models": {id: model()}}} -> a RemoteLookup."""

    def build(providers: dict) -> RemoteLookup:
        return RemoteLookup(
            RemoteManifest.model_validate(
                {
                    "schema_version": 1,
                    "source": "https://models.dev/api.json",
                    "refreshed_at": "2026-09-23",
                    "providers": {
                        name: {
                            "name": name.title(),
                            "doc": None,
                            "connect": spec.get("connect", connect()),
                            "models": spec["models"],
                        }
                        for name, spec in providers.items()
                    },
                }
            )
        )

    return build
