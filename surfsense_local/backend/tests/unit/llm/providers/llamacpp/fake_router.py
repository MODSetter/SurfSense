"""A stand-in for llama-server in router mode.

Shapes come from the real thing at b11050: `/models` reports each discovered
model with a `status` carrying the worker's argv, which is the only reliable way
to see what the router actually did with a load request.
"""

import json

import httpx


class FakeRouter:
    """Records what was asked of it, so tests can assert on the calls."""

    def __init__(self, models: list[str] | None = None) -> None:
        self.models = models or []
        self.loaded: set[str] = set()
        self.deleted: list[str] = []
        self.chat_bodies: list[dict] = []
        # What `/props` reports about the chat template. Defaults to a template
        # that carries everything, which is the common case.
        self.template_caps: dict = {"supports_system_role": True}
        # llama.cpp issue #29006: some templates 400 on a json_schema request.
        self.reject_response_format = False
        self.fail_chat_with: int | None = None
        # A thinking model. Measured against Qwen3 1.7B at b11050 with
        # `--reasoning-format deepseek`: every token of the trace arrives as
        # `reasoning_content`, and a short `max_tokens` is spent before a
        # single `content` token exists.
        self.thinks = False
        # What `/tokenize` reports for one content-encoded token, so a test
        # can make the fake count deterministically instead of running a
        # real tokenizer.
        self.tokens_per_word = 1
        # How many times `/props` was actually asked, so a test can tell a
        # cached read apart from a fresh round trip.
        self.props_calls = 0

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/props":
            self.props_calls += 1
            return httpx.Response(
                200,
                json={
                    "role": "router",
                    "chat_template_caps": self.template_caps,
                    "default_generation_settings": {"n_ctx": 16384},
                },
            )
        if path == "/models" and request.method == "GET":
            return httpx.Response(200, json={"object": "list", "data": [
                {
                    "id": name,
                    "status": {
                        "value": "loaded" if name in self.loaded else "unloaded",
                        "args": ["llama-server", "--alias", name],
                    },
                }
                for name in self.models
            ]})
        if path == "/models" and request.method == "DELETE":
            # The real router refuses anything it did not download into its own
            # cache. Measured: `model name=... is not removable (not from
            # cache)`, 500. Everything SurfSense installs lands in --models-dir,
            # so this always refuses, and a fake that said otherwise is what let
            # a broken delete path ship.
            self.deleted.append(request.url.params.get("model", ""))
            return httpx.Response(
                500,
                json={
                    "error": {
                        "code": 500,
                        "message": "model name=x is not removable (not from cache)",
                        "type": "server_error",
                    }
                },
            )
        if path == "/models/load":
            self.loaded.add(json.loads(request.content)["model"])
            return httpx.Response(200, json={"success": True})
        if path == "/models/unload":
            self.loaded.discard(json.loads(request.content)["model"])
            return httpx.Response(200, json={"success": True})
        if path == "/tokenize":
            body = json.loads(request.content)
            words = body.get("content", "").split()
            return httpx.Response(
                200, json={"tokens": list(range(len(words) * self.tokens_per_word))}
            )
        if path == "/v1/chat/completions":
            body = json.loads(request.content)
            self.chat_bodies.append(body)
            if self.fail_chat_with is not None:
                return httpx.Response(self.fail_chat_with, json={"error": "nope"})
            if self.reject_response_format and "response_format" in body:
                return httpx.Response(
                    400, json={"error": {"message": "unsupported response_format"}}
                )
            chunks = _stream(self.thinks and not _thinking_off(body))
            return httpx.Response(
                200,
                text="\n\n".join(chunks) + "\n\n",
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(404, json={"error": path})


def _thinking_off(body: dict) -> bool:
    """Either mechanism alone stops the trace, which is why both are sent.

    The real server reads them independently: one is a chat template variable,
    the other is its own end of thinking injection.
    """
    kwargs = body.get("chat_template_kwargs") or {}
    return body.get("thinking_budget_tokens") == 0 or kwargs.get(
        "enable_thinking"
    ) is False


def _stream(thinking: bool) -> list[str]:
    """What a thinking model emits, against what one answering plainly does."""
    if thinking:
        return [
            'data: {"choices":[{"delta":{"reasoning_content":"Okay, the user"}}]}',
            'data: {"choices":[{"finish_reason":"length","delta":{}}]}',
            "data: [DONE]",
        ]
    return [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        "data: [DONE]",
    ]
