from modules.llm.models import ProviderConnection
from modules.llm.providers.elevenlabs.account import ELEVENLABS
from modules.llm.providers.elevenlabs.speech import ElevenLabsSpeech
from modules.llm.providers.openai_compatible.speech import RemoteSpeech
from modules.llm.providers.protocols import TextToSpeech


def speech_client(connection: ProviderConnection, model: str) -> TextToSpeech:
    """What voices `model` on this connection: the one rule podcasts and tests share."""
    client = ElevenLabsSpeech if connection.auth_kind == ELEVENLABS else RemoteSpeech
    return client(model, base_url=connection.base_url, api_key=connection.api_key)
