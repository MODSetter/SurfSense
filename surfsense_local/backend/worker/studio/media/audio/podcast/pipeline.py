import asyncio
import logging

from modules.llm.providers.protocols import SpokenTurn, TextToSpeech
from modules.llm.resolution import ResolvedGeneration, resolve_text_to_speech
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

logger = logging.getLogger(__name__)

_EXTENSIONS = {"audio/wav": "wav", "audio/mpeg": "mp3", "audio/ogg": "ogg"}

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "turns": '
    '[{"speaker": "A" | "B", "text": str}]}.'
)


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Centre it on: {user_prompt}." if user_prompt else ""
    return (
        "Write a two-host podcast conversation about the sources below, using "
        "their facts only. Host A leads, host B reacts and asks; keep turns "
        "short and natural." + focus + " " + _SCHEMA
    )


def build(raw: str, voice: TextToSpeech) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Podcast"
    # One voice per host from whatever the engine offers; B falls back to A's
    # voice on a single-voice engine, and unknown speakers read as host A.
    voices = voice.voices()
    hosts = {"A": voices[0].id, "B": voices[-1].id}

    transcript = [f"# {title}", ""]
    turns: list[SpokenTurn] = []
    for turn in as_list(spec.get("turns")):
        if not isinstance(turn, dict):
            continue
        speaker = (as_text(turn.get("speaker")) or "A").upper()[:1]
        text = as_text(turn.get("text"))
        if not text:
            continue
        transcript.append(f"**{speaker}:** {text}")
        transcript.append("")
        turns.append(SpokenTurn(hosts.get(speaker, hosts["A"]), text))

    logger.info(
        "studio: podcast %s turns (%s spoken chars); synthesising",
        len(turns),
        sum(len(turn.text) for turn in turns),
    )
    audio = asyncio.run(voice.synthesize(turns))
    extension = _EXTENSIONS.get(audio.media_type, "bin")
    return Built(
        title=title,
        markdown="\n".join(transcript).strip(),
        primary=audio.content,
        primary_mime=audio.media_type,
        primary_filename=f"{slug(title, 'podcast')}.{extension}",
    )


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    """Write the transcript with the generation model, then voice it."""
    # The voice engine is checked first so a missing one never costs a model call.
    voice = resolve_text_to_speech()
    raw = generate.run_model(model, prompt(sources, user_prompt), sources)
    return build(raw, voice)
