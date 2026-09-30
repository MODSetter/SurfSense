from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.egress import service as egress
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.catalog.remote.reads_images import remote_reads_images
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.profile import Tier
from modules.llm.providers import audiocpp, get_provider, llamacpp
from modules.llm.providers.audiocpp.speech import AudioCppSpeech, VoicedModel
from modules.llm.providers.openai_compatible import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleImageProvider,
)
from modules.llm.providers.openai_compatible.speech import RemoteSpeech
from modules.llm.providers.protocols import Generator, ImageGenerator, TextToSpeech
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.providers.sdcpp.generator import LocalImageGenerator
from shared.config import get_llm_settings


class ModelResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedGeneration:
    selection: SelectedModel
    generator: Generator

    @property
    def tier(self) -> Tier:
        """Which prompt every case writing through this model should load."""
        return self.selection.tier


@dataclass(frozen=True)
class ResolvedImageGeneration:
    selection: SelectedModel
    generator: ImageGenerator


def resolve_generation(session: Session) -> ResolvedGeneration:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        raise ModelResolutionError("no chat model selected")
    if selected.provider == llamacpp.PROVIDER:
        provider = get_provider(llamacpp.PROVIDER)
        if provider is None:  # pragma: no cover - fixed registry invariant
            raise ModelResolutionError("the local runtime is unavailable")
        return ResolvedGeneration(selected, provider)
    connection = _connection(session, selected)
    return ResolvedGeneration(
        selected,
        OpenAICompatibleChatProvider(
            connection.base_url,
            connection.api_key,
            reads_images=remote_reads_images(
                selected.name, connection.catalog_provider
            ),
        ),
    )


def resolve_image_generation(session: Session) -> ResolvedImageGeneration:
    selected = session.get(SelectedModel, ModelType.IMAGE_GEN)
    if selected is None:
        raise ModelResolutionError("no image model selected")
    if selected.provider == sdcpp.PROVIDER:
        image = get_local_catalog().sdcpp.installed_image(selected.name)
        if image is None:
            raise ModelResolutionError("the local image model is not installed")
        # sd-server speaks /images/generations, so the OpenAI-compatible client
        # reaches it unchanged, once it is up on this model. Connection id 0: it
        # has no connection row, and the id only keys that client's route cache.
        return ResolvedImageGeneration(
            selected,
            LocalImageGenerator(
                OpenAICompatibleImageProvider(0, sdcpp.base_url(), None),
                sdcpp.root_url(),
                image.served_file,
                llamacpp.RouterClient(get_llm_settings().llamacpp_base_url),
            ),
        )
    connection = _connection(session, selected)
    return ResolvedImageGeneration(
        selected,
        OpenAICompatibleImageProvider(
            connection.id, connection.base_url, connection.api_key
        ),
    )


def speech_selected(session: Session) -> None:
    """Raise unless the chosen audio model can be reached for, without reaching
    it: the format list asks, and must not call a server to answer."""
    selected = selected_audio(session)
    if selected.provider == audiocpp.PROVIDER:
        local_speech(selected)
    else:
        stored_connection(session, selected)


def resolve_text_to_speech(session: Session) -> TextToSpeech:
    selected = selected_audio(session)
    if selected.provider == audiocpp.PROVIDER:
        return local_speech(selected)
    return _remote_speech(selected, _connection(session, selected))


def _remote_speech(
    selected: SelectedModel, connection: ProviderConnection
) -> RemoteSpeech:
    return RemoteSpeech(
        selected.name,
        base_url=connection.base_url,
        api_key=connection.api_key,
    )


def selected_audio(session: Session) -> SelectedModel:
    selected = session.get(SelectedModel, ModelType.AUDIO_GEN)
    if selected is None:
        raise ModelResolutionError("no audio model selected")
    return selected


def local_speech(selected: SelectedModel) -> AudioCppSpeech:
    engine = get_local_catalog().audiocpp
    installed = engine.installed_model(selected.name)
    if installed is None:
        raise ModelResolutionError("the local audio model is not installed")
    voiced = VoicedModel(
        installed.model_id, installed.audio, engine.others_than(installed)
    )
    return AudioCppSpeech(
        voiced,
        base_url=audiocpp.base_url(),
        chat_runtime=llamacpp.RouterClient(get_llm_settings().llamacpp_base_url),
    )


def _connection(session: Session, selected: SelectedModel) -> ProviderConnection:
    """The selection's connection, once egress to its host is allowed."""
    connection = stored_connection(session, selected)
    egress.require(session, egress.host_destination(connection.base_url))
    return connection


def stored_connection(session: Session, selected: SelectedModel) -> ProviderConnection:
    if selected.provider != "openai_compatible" or selected.connection_id is None:
        raise ModelResolutionError(f"unknown provider: {selected.provider}")
    connection = session.get(ProviderConnection, selected.connection_id)
    if connection is None:
        raise ModelResolutionError("selected model connection no longer exists")
    return connection
