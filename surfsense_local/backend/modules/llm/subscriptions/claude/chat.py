import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

from claude_agent_sdk import ResultMessage, StreamEvent, SystemMessage

from modules.egress.service import EgressDeniedError
from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.reads_images import remote_reads_images
from modules.llm.model_type import ModelType
from modules.llm.providers.openai_compatible.chat import (
    BETWEEN_TOKENS_SECONDS,
    FIRST_TOKEN_SECONDS,
)
from modules.llm.providers.stream_deadline import with_deadlines
from modules.llm.providers.types import Delta, Message, Model
from modules.llm.subscriptions.claude.account import CATALOG_PROVIDER
from modules.llm.subscriptions.claude.chat_prompt import system_prompt
from modules.llm.subscriptions.claude.chat_runs import ChatRuns
from modules.llm.subscriptions.claude.errors import (
    ClaudeSignInRequiredError,
    failure_of,
)
from modules.llm.subscriptions.claude.launch import launch_options
from modules.llm.subscriptions.claude.locate import this_machines_claude
from modules.llm.subscriptions.claude.models import claude_models
from modules.llm.subscriptions.claude.run import ClaudeRun, Prompt
from modules.llm.subscriptions.claude.status import ClaudeState, read_status

# Claude Code returns a schema's answer through a tool of its own, which takes
# a second turn; measured, one call in four used a third.
_TURNS_FOR_A_SCHEMA = 3

ProxyRefusal = Callable[[], Awaitable[EgressDeniedError | None]]


async def _no_refusal() -> EgressDeniedError | None:
    return None


class ClaudePlanProvider:
    """A Generator over the user's own Claude Code with every tool off (ADR 0052).

    A token cap and a temperature are accepted and dropped: Claude Code exposes
    neither.
    """

    name = "claude_plan"

    def __init__(
        self,
        *,
        runs: ChatRuns,
        work_dir: Path,
        find_claude: Callable[[], Path | None] = this_machines_claude,
        proxy_url: Callable[[], str | None] = lambda: None,
        proxy_refusal: ProxyRefusal = _no_refusal,
    ) -> None:
        self._runs = runs
        # Empty, so no project file is near the run.
        self._work_dir = work_dir
        self._find_claude = find_claude
        # Read when a run starts, so a missing proxy refuses that run, not the resolver.
        self._proxy_url = proxy_url
        # Asked only when Claude Code retries, whether a Claude host is off.
        self._proxy_refusal = proxy_refusal

    def _binary(self) -> Path:
        binary = self._find_claude()
        if binary is None:
            raise ClaudeSignInRequiredError("Claude Code is not installed")
        return binary

    async def health(self) -> bool:
        try:
            proxy_url = self._proxy_url()
        except RuntimeError:
            return False
        found = await asyncio.to_thread(
            read_status, self._find_claude(), proxy_url=proxy_url
        )
        return found.state is ClaudeState.READY

    async def models(self) -> list[Model]:
        return [
            Model(m.name, installed=True, types=(ModelType.TEXT_GEN,))
            for m in await claude_models(self._binary(), self._proxy_url())
        ]

    async def context_tokens(self, model: str) -> int | None:
        found = remote_lookup().classify(model, provider=CATALOG_PROVIDER)
        return found.supports.context_window if found.supports else None

    async def sees_images(self, model: str) -> bool | None:
        return remote_reads_images(model, CATALOG_PROVIDER)

    async def token_count(self, model: str, text: str) -> int | None:
        return None

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
        json_schema: dict | None = None,
        conversation: str | None = None,
    ) -> AsyncIterator[str]:
        async for delta in self.chat_deltas(
            model,
            messages,
            reasoning=reasoning,
            json_schema=json_schema,
            conversation=conversation,
        ):
            if not delta.reasoning:
                yield delta.text

    async def chat_deltas(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
        json_schema: dict | None = None,
        conversation: str | None = None,
    ) -> AsyncIterator[Delta]:
        options = launch_options(
            self._binary(),
            proxy_url=self._proxy_url(),
            model=model,
            tools=[],
            max_turns=_TURNS_FOR_A_SCHEMA if json_schema is not None else 1,
            system_prompt=system_prompt(messages),
            include_partial_messages=True,
            extra_args={"no-session-persistence": None},
            cwd=str(self._work_dir),
            # Without `summarized`, Claude Code omits the thinking text.
            thinking={"type": "adaptive", "display": "summarized"}
            if reasoning
            else None,
            output_format={"type": "json_schema", "schema": json_schema}
            if json_schema is not None
            else None,
        )
        settings = (model, bool(reasoning), json.dumps(json_schema, sort_keys=True))
        async with self._runs.turn(conversation, settings, options, messages) as (
            run,
            prompt,
        ):
            async for delta in with_deadlines(
                _answer(
                    run,
                    prompt,
                    structured=json_schema is not None,
                    proxy_refusal=self._proxy_refusal,
                ),
                first_item_seconds=FIRST_TOKEN_SECONDS,
                between_items_seconds=BETWEEN_TOKENS_SECONDS,
                subject="Claude Code",
            ):
                yield delta


async def _answer(
    run: ClaudeRun, prompt: Prompt, *, structured: bool, proxy_refusal: ProxyRefusal
) -> AsyncIterator[Delta]:
    async for message in run.send(prompt):
        retrying = isinstance(message, SystemMessage) and message.subtype == "api_retry"
        refusal = await proxy_refusal() if retrying else None
        if (failure := failure_of(message, proxy_refusal=refusal)) is not None:
            raise failure
        if isinstance(message, ResultMessage):
            if structured:
                yield Delta(json.dumps(message.structured_output))
            return
        if structured or not isinstance(message, StreamEvent):
            continue
        event = message.event
        if event.get("type") != "content_block_delta":
            continue
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            yield Delta(delta["text"])
        elif delta.get("type") == "thinking_delta":
            yield Delta(delta["thinking"], reasoning=True)
