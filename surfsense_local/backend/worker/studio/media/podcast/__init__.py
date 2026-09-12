import logging

from worker.studio.artifact import Built, Source
from worker.studio.builder import Builder
from worker.studio.text import as_list, as_text, parse_json, slug

logger = logging.getLogger(__name__)

MIME = "audio/wav"

# Two Kokoro voices, one per host. Speakers beyond A/B fall back to the host voice.
_VOICES = {"A": "af_heart", "B": "am_adam"}

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


def build(raw: str, _sources: list[Source]) -> Built:
    from worker.studio.media.podcast import tts

    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Podcast"

    transcript = [f"# {title}", ""]
    turns: list[tts.Turn] = []
    for turn in as_list(spec.get("turns")):
        if not isinstance(turn, dict):
            continue
        speaker = (as_text(turn.get("speaker")) or "A").upper()[:1]
        text = as_text(turn.get("text"))
        if not text:
            continue
        transcript.append(f"**{speaker}:** {text}")
        transcript.append("")
        turns.append(tts.Turn(_VOICES.get(speaker, _VOICES["A"]), text))

    logger.info(
        "studio: podcast %s turns (%s spoken chars); calling kokoro",
        len(turns),
        sum(len(turn.text) for turn in turns),
    )
    audio = tts.synthesize(turns)
    return Built(
        title=title,
        markdown="\n".join(transcript).strip(),
        primary=audio,
        primary_mime=MIME,
        primary_filename=f"{slug(title, 'podcast')}.wav",
    )


builder = Builder(key="podcast", prompt=prompt, build=build)
