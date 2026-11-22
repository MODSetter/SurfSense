from typing import Annotated

from fastapi import Depends, Request

from modules.llm.providers.protocols import Transcriber
from modules.llm.transcription import http_errors
from modules.llm.transcription.gate import TranscriptionGate
from modules.llm.transcription.server import transcriber_here
from modules.llm.transcription.sessions import DictationSessions


def get_gate(request: Request) -> TranscriptionGate:
    """The app's one gate: every request to the transcription server waits in it."""
    return request.app.state.transcription_gate


def get_dictations(request: Request) -> DictationSessions:
    return request.app.state.dictations


def get_transcriber() -> Transcriber:
    transcriber = transcriber_here()
    if transcriber is None:
        raise http_errors.transcription_unavailable("this build has no audio.cpp")
    return transcriber


GateDep = Annotated[TranscriptionGate, Depends(get_gate)]
DictationsDep = Annotated[DictationSessions, Depends(get_dictations)]
TranscriberDep = Annotated[Transcriber, Depends(get_transcriber)]
