"""An opener that answers urllib requests from a table, as GitHub or PostHog would."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class FakeResponse:
    def __init__(self, body: Any, link: str | None = None) -> None:
        self._body = json.dumps(body).encode()
        self.headers = {"Link": link} if link else {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class FakeOpener:
    """Answers each URL with ``(body, link)``, or raises its status if it is an int."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        answer = self.routes.get(request.full_url, ({}, None))
        if isinstance(answer, int):
            raise urllib.error.HTTPError(request.full_url, answer, "refused", {}, None)
        body, link = answer
        return FakeResponse(body, link)
