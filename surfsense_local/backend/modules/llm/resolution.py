from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.egress import service as egress
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.catalog.local.engines.audiocpp.audio_folder.installed_recognisers import (
    InstalledRecogniser,
)
from modules.llm.catalog.remote.reads_images import remote_reads_images
from modules.llm.connections.serves import connection_serves
from modules.llm.connections.text_generator import connection_generator
from modules.llm.model_route.runtime_hold import text_runtime_given_up
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.profile import Tier
from modules.llm.providers import audiocpp, get_provider, llamacpp
from modules.llm.providers.audiocpp.speech import AudioCppSpeech, VoicedModel
from modules.llm.providers.openai_compatible import (
    NonRetryableImageError,
    OpenAICompatibleImageProvider,
)
from modules.llm.providers.openai_compatible.image import AllowUrlHost
from modules.llm.providers.openai_compatible.speech import RemoteSpeech
from modules.llm.providers.protocols import Generator, ImageGenerator, TextToSpeech
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.providers.sdcpp.generator import LocalImageGenerator
from modules.llm.subscriptions.claude.account import CLAUDE_PLAN
from modules.llm.subscriptions.claude.hosts import require_claude_hosts
from modules.llm.subscriptions.claude.usable_claude import usable_claude


class ModelResolutionError(RuntimeError):
    pass


class NoSpeechModelError(ModelResolutionError):
    """No speech model is chosen, or the chosen one is no longer installed."""


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


@dataclass(frozen=True)
class ResolvedSpeechToText:
    selection: SelectedModel
    # The installed file and the reviewed languages the client is built from.
    recogniser: InstalledRecogniser


def resolve_generation(session: Session) -> ResolvedGeneration:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        raise ModelResolutionError("no chat model selected")
    return resolve_generation_of(session, selected)


def resolve_generation_of(
    session: Session, selected: SelectedModel
) -> ResolvedGeneration:
    """A text model reachable as `selected` describes it, selected or not."""
    if selected.provider == llamacpp.PROVIDER:
        provider = get_provider(llamacpp.PROVIDER)
        if provider is None:  # pragma: no cover - fixed registry invariant
            raise ModelResolutionError("the local runtime is unavailable")
        return ResolvedGeneration(selected, provider)
    connection = _connection(session, selected)
    reads_images = remote_reads_images(selected.name, connection.catalog_provider)
    return ResolvedGeneration(
        selected,
        connection_generator(
            session.get_bind(), connection, selected.name, reads_images=reads_images
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
                OpenAICompatibleImageProvider(
                    0,
                    sdcpp.base_url(),
                    None,
                    allow_url_host=_allow_url_host(session),
                ),
                sdcpp.root_url(),
                image.served_file,
                text_runtime_given_up,
            ),
        )
    connection = _connection(session, selected)
    _require_serves(connection, ModelType.IMAGE_GEN)
    return ResolvedImageGeneration(
        selected,
        OpenAICompatibleImageProvider(
            connection.id,
            connection.base_url,
            connection.api_key,
            allow_url_host=_allow_url_host(session),
        ),
    )


def _allow_url_host(session: Session) -> AllowUrlHost:
    """The egress check for an image's URL, run in the Studio worker's thread."""

    async def allow(url: str) -> None:
        refused = egress.refused_named_host(session, url)
        session.commit()
        if refused is not None:
            # No dialog reaches the worker, so the job fails with the refusal as
            # its reason. The image was already generated, and billed, before
            # its URL was known: a retry would pay again for the same refusal.
            raise NonRetryableImageError(str(refused)) from refused

    return allow


def speech_selected(session: Session) -> None:
    """Raise unless the chosen audio model can be reached for, without reaching
    it: the format list asks, and must not call a server to answer."""
    selected = selected_audio(session)
    if selected.provider == audiocpp.PROVIDER:
        local_speech(selected)
    else:
        _require_serves(stored_connection(session, selected), ModelType.AUDIO_GEN)


def resolve_text_to_speech(session: Session) -> TextToSpeech:
    selected = selected_audio(session)
    if selected.provider == audiocpp.PROVIDER:
        return local_speech(selected)
    connection = _connection(session, selected)
    _require_serves(connection, ModelType.AUDIO_GEN)
    return _remote_speech(selected, connection)


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
        give_up_text_runtime=text_runtime_given_up,
    )


def resolve_speech_to_text(session: Session) -> ResolvedSpeechToText:
    """The chosen speech model as the transcription server runs it. Local only:
    no remote speech client exists."""
    selected = session.get(SelectedModel, ModelType.SPEECH_TO_TEXT)
    if selected is None or selected.provider != audiocpp.PROVIDER:
        raise NoSpeechModelError("no speech model selected")
    recogniser = get_local_catalog().audiocpp.installed_recogniser(selected.name)
    if recogniser is None:
        raise NoSpeechModelError("the speech model is not installed")
    return ResolvedSpeechToText(selected, recogniser)


def _require_serves(connection: ProviderConnection, model_type: ModelType) -> None:
    if model_type not in connection_serves(connection):
        raise ModelResolutionError(f"this connection does not serve {model_type.value}")


def _connection(session: Session, selected: SelectedModel) -> ProviderConnection:
    """The selection's connection, once egress to its host is allowed."""
    connection = stored_connection(session, selected)
    egress.require(session, egress.host_destination(connection.base_url))
    if connection.auth_kind == CLAUDE_PLAN:
        # Claude Code also refreshes its sign-in on a host of its own.
        require_claude_hosts(session)
        # Before anything streams, so the send is refused and the composer says why.
        usable_claude()
    return connection


def stored_connection(session: Session, selected: SelectedModel) -> ProviderConnection:
    if selected.provider != "openai_compatible" or selected.connection_id is None:
        raise ModelResolutionError(f"unknown provider: {selected.provider}")
    connection = session.get(ProviderConnection, selected.connection_id)
    if connection is None:
        raise ModelResolutionError("selected model connection no longer exists")
    return connection
