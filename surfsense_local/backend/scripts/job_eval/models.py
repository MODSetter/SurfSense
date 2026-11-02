"""The models an eval row is measured on, each answering the runner's one question at a time.

Claude goes through Anthropic's Messages API with structured outputs; open models through
OpenRouter's chat completions with a JSON schema. Neither falls back to another model on a
refusal or an error: a row measures the model it names, and a failure counts against it.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

import httpx

from modules.jobs.workbook_rows.ask import ModelReply

# As the app's job allows, so a thinking model's reasoning fits before its answer.
MAX_TOKENS = 8192
CALL_SECONDS = 180.0
RETRIES = 3
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
# Anthropic list prices, $ per million tokens (cached 2026-10-06): input, output.
ANTHROPIC_PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
# Opus and Fable are never run here: their price is out of proportion to an eval row.
REFUSED_MODELS = ("opus", "fable", "mythos")


@dataclass
class Spend:
    """What one model's calls cost, summed across threads."""

    calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    dollars: float = 0.0
    errors: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, *, inputs: int, cached: int, outputs: int, dollars: float) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += inputs
            self.cached_tokens += cached
            self.output_tokens += outputs
            self.dollars += dollars


def model_for(spec: str, *, concurrency: int, effort: str, reasoning: str):
    """`anthropic:<model id>` or `openrouter:<model id>`; keys come from the environment."""
    provider, _, model_id = spec.partition(":")
    if any(word in model_id.casefold() for word in REFUSED_MODELS):
        raise SystemExit(f"{model_id}: eval rows never run on Opus, Fable or Mythos.")
    if provider == "anthropic":
        return AnthropicModel(
            model_id, os.environ["ANTHROPIC_API_KEY"], concurrency, effort
        )
    if provider == "openrouter":
        return OpenRouterModel(
            model_id, os.environ["OPENROUTER_API_KEY"], concurrency, reasoning
        )
    raise SystemExit(f"{spec}: name the model as anthropic:<id> or openrouter:<id>.")


class AnthropicModel:
    window = 1_000_000

    def __init__(self, model_id: str, key: str, concurrency: int, effort: str) -> None:
        import anthropic

        self.name = model_id
        self.concurrency = concurrency
        self.effort = effort
        self.spend = Spend()
        self._client = anthropic.Anthropic(
            api_key=key, timeout=CALL_SECONDS, max_retries=RETRIES
        )

    def ask(
        self, system: str, turns: list[tuple[str, str]], schema: dict, shared: int
    ) -> ModelReply:
        messages = [
            {"role": role, "content": _blocks(text, shared if index == 0 else 0)}
            for index, (role, text) in enumerate(turns)
        ]
        response = self._client.messages.create(
            model=self.name,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={
                "format": {"type": "json_schema", "schema": schema},
                "effort": self.effort,
            },
        )
        usage = response.usage
        written = usage.cache_creation_input_tokens or 0
        read = usage.cache_read_input_tokens or 0
        price_in, price_out = ANTHROPIC_PRICES.get(self.name, (0.0, 0.0))
        self.spend.add(
            inputs=usage.input_tokens + written + read,
            cached=read,
            outputs=usage.output_tokens,
            dollars=(
                usage.input_tokens * price_in
                + written * price_in * 1.25
                + read * price_in * 0.1
                + usage.output_tokens * price_out
            )
            / 1_000_000,
        )
        if response.stop_reason == "refusal":
            self.spend.errors.append("refusal")
            return ModelReply("", usage.input_tokens, usage.output_tokens)
        text = "".join(block.text for block in response.content if block.type == "text")
        return ModelReply(
            text, usage.input_tokens + written + read, usage.output_tokens
        )


class OpenRouterModel:
    window = 131_072

    def __init__(
        self, model_id: str, key: str, concurrency: int, reasoning: str
    ) -> None:
        self.name = model_id
        self.concurrency = concurrency
        self.reasoning = reasoning
        self.spend = Spend()
        self._client = httpx.Client(
            timeout=httpx.Timeout(CALL_SECONDS, connect=15.0),
            headers={"Authorization": f"Bearer {key}", "X-Title": "SurfSense job eval"},
        )

    def ask(
        self, system: str, turns: list[tuple[str, str]], schema: dict, shared: int
    ) -> ModelReply:
        body = {
            "model": self.name,
            "messages": [
                {"role": "system", "content": system},
                *(
                    {
                        "role": role,
                        "content": _blocks(text, shared if index == 0 else 0),
                    }
                    for index, (role, text) in enumerate(turns)
                ),
            ],
            "max_tokens": MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": schema},
            },
            # Only providers that honour the schema; one that ignored it would score its parse.
            "provider": {"require_parameters": True},
            "usage": {"include": True},
        }
        # "default" sends nothing, as the app's connection does: the model thinks if it does.
        if self.reasoning != "default":
            body["reasoning"] = {"enabled": self.reasoning == "on"}
        reply = self._post(body)
        usage = reply.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        self.spend.add(
            inputs=usage.get("prompt_tokens") or 0,
            cached=cached,
            outputs=usage.get("completion_tokens") or 0,
            dollars=float(usage.get("cost") or 0.0),
        )
        choice = (reply.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        return ModelReply(
            text, usage.get("prompt_tokens"), usage.get("completion_tokens")
        )

    def _post(self, body: dict) -> dict:
        for attempt in range(RETRIES + 1):
            try:
                response = self._client.post(OPENROUTER, json=body)
                if response.status_code == 200:
                    reply = response.json()
                    if "error" not in reply:
                        return reply
                    problem = str(reply["error"])[:300]
                elif response.status_code in (408, 429) or response.status_code >= 500:
                    problem = f"HTTP {response.status_code}: {response.text[:300]}"
                else:
                    response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError) as failure:
                problem = f"{type(failure).__name__}: {failure}"
            self.spend.errors.append(problem)
            time.sleep(2 * (attempt + 1))
        return {"choices": [{"message": {"content": ""}}]}


def _blocks(text: str, shared: int) -> list[dict]:
    """The first turn split where every question repeats it, the repeated part marked for caching."""
    if 0 < shared < len(text):
        return [
            {
                "type": "text",
                "text": text[:shared],
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": text[shared:]},
        ]
    return [{"type": "text", "text": text}]
