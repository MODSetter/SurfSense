"""Where a model answers: the app's llama-server, or Featherless."""

import os
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from chat_eval.model import EvalModel
from chat_eval.request import body
from modules.llm.providers.llamacpp.capabilities import read_capabilities
from modules.llm.providers.llamacpp.messages import for_template
from modules.llm.providers.llamacpp.router_client import RouterClient
from modules.llm.providers.types import Message

FEATHERLESS_URL = "https://api.featherless.ai/v1"
# One read carries the whole reply: up to 1,024 tokens of a thinking model, maybe
# on a CPU.
TIMEOUT = httpx.Timeout(900.0, connect=10.0)


@dataclass(frozen=True)
class Target:
    name: str
    base_url: str
    # The model's name on this target.
    model: str
    # The llama.cpp build that answers, when the target reports one.
    runtime: str | None = None
    api_key: str | None = None
    # What this target's template needs done to the conversation.
    shape: Callable[[list[Message]], list[Message]] = list


@dataclass(frozen=True)
class Reply:
    content: str
    reasoning_chars: int
    finish_reason: str | None
    usage: dict
    timings: dict


async def local(base_url: str, model: EvalModel) -> Target:
    """The app's llama-server, with the model loaded and its template read as chat does."""
    router = RouterClient(base_url)
    if model.local_name not in {listed.id for listed in await router.models()}:
        raise ValueError(
            f"{model.local_name} is not in the models folder: "
            f"install {model.id}'s default build in the app"
        )
    await router.load(model.local_name)
    props = await router.props(model.local_name)
    capabilities = read_capabilities(model.local_name, await router.raw_models(), props)
    return Target(
        name="local",
        base_url=f"{base_url.rstrip('/')}/v1",
        model=model.local_name,
        runtime=props.get("build_info"),
        shape=lambda messages: for_template(messages, capabilities),
    )


def featherless(model: EvalModel) -> Target:
    api_key = os.environ.get("FEATHERLESS_API_KEY")
    if not api_key:
        raise ValueError("set FEATHERLESS_API_KEY to run on Featherless")
    return Target(
        name="featherless",
        base_url=FEATHERLESS_URL,
        model=model.featherless_name,
        api_key=api_key,
    )


async def ask(
    target: Target, messages: list[Message], sampling: dict[str, float | int]
) -> Reply:
    headers = {"Authorization": f"Bearer {target.api_key}"} if target.api_key else {}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
        response = await client.post(
            f"{target.base_url}/chat/completions",
            json=body(target.model, target.shape(messages), sampling),
        )
    if response.is_error:
        raise RuntimeError(
            f"{target.name} answered {response.status_code}: {response.text[:400]}"
        )
    payload = response.json()
    choice = payload["choices"][0]
    message = choice.get("message") or {}
    # llama.cpp calls it reasoning_content; some OpenAI-style hosts call it reasoning.
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    return Reply(
        content=message.get("content") or "",
        reasoning_chars=len(reasoning),
        finish_reason=choice.get("finish_reason"),
        usage=payload.get("usage") or {},
        timings=payload.get("timings") or {},
    )
