import asyncio

import httpx
from sqlalchemy.orm import Session

from modules.llm.connections.service import DiscoveredModel, discover_models
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection
from modules.llm.providers.elevenlabs.account import (
    ELEVENLABS,
    account_voices,
    text_to_speech_models,
)
from modules.llm.subscriptions.chatgpt.account import CHATGPT
from modules.llm.subscriptions.chatgpt.plan_models import plan_models
from modules.llm.subscriptions.claude.account import CLAUDE_PLAN
from modules.llm.subscriptions.claude.models import claude_models
from modules.llm.subscriptions.claude.proxy import required_claude_proxy_url
from modules.llm.subscriptions.claude.usable_claude import usable_claude
from modules.llm.voices.voice import Voice


async def connection_models(
    session: Session, connection: ProviderConnection
) -> list[DiscoveredModel]:
    """What a connection offers: its plan's list when signed in with ChatGPT,
    Claude Code's list for a Claude plan, its server's `/models` otherwise."""
    if connection.auth_kind == CHATGPT:
        return await plan_models(session.get_bind(), connection)
    if connection.auth_kind == CLAUDE_PLAN:
        binary = await asyncio.to_thread(usable_claude)
        return await claude_models(binary, required_claude_proxy_url())
    if connection.auth_kind == ELEVENLABS:
        return await asyncio.to_thread(
            _elevenlabs_models, connection.base_url, connection.api_key
        )
    return await discover_models(connection)


def _elevenlabs_models(base_url: str, api_key: str | None) -> list[DiscoveredModel]:
    """Its voices are the account's, not a model's; losing them leaves a typed id."""
    models = text_to_speech_models(base_url, api_key)
    try:
        voices: list[Voice] = account_voices(base_url, api_key, ())
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        voices = []
    return [
        DiscoveredModel(
            model.id,
            (ModelType.AUDIO_GEN,),
            "declared",
            voices=tuple(voices),
        )
        for model in models
    ]
