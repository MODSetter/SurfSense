from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "cards": '
    '[{"front": str, "back": str}]}.'
)


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    return build(
        generate.run_model(model, prompt(sources, user_prompt), sources), sources
    )


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Focus on: {user_prompt}." if user_prompt else ""
    return (
        "Make study flashcards from the sources below — a prompt on the front, "
        "the answer on the back, using their facts only." + focus + " " + _SCHEMA
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Flashcards"
    lines = [f"# {title}", ""]

    for index, card in enumerate(as_list(spec.get("cards")), start=1):
        if not isinstance(card, dict):
            continue
        front = as_text(card.get("front"))
        back = as_text(card.get("back"))
        if front and back:
            lines.append(f"**{index}. {front}**")
            lines.append("")
            lines.append(back)
            lines.append("")

    return Built(title=title, markdown="\n".join(lines).strip())
