from collections.abc import Iterator

import pytest

from modules.llm.subscriptions.chatgpt.endpoints import get_endpoints

from .fake_openai import FakeOpenAI


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeOpenAI]:
    """OpenAI's sign-in and plan endpoints, with the app pointed at them."""
    fake = FakeOpenAI()
    fake.start()
    endpoints = get_endpoints()
    monkeypatch.setattr(endpoints, "auth_url", fake.url)
    monkeypatch.setattr(endpoints, "api_url", f"{fake.url}/v1")
    yield fake
    fake.stop()
