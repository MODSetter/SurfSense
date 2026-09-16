import json

from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "cards": '
    '[{"front": str, "back": str}]}. '
    "Content is plain text. The only formatting syntax is LaTeX: use \\(...\\) "
    "for inline math and \\[...\\] for display math. Escape each backslash as "
    "\\\\ in JSON. Keep delimiters and braces balanced and do not nest math "
    "delimiters."
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
    cards = []

    for card in as_list(spec.get("cards")):
        if not isinstance(card, dict):
            continue
        front = as_text(card.get("front"))
        back = as_text(card.get("back"))
        if front and back:
            cards.append({"front_text": front, "back_text": back})
            lines += [f"**{len(cards)}. {front}**", "", back, ""]

    deck = {"schema_version": 1, "title": title, "cards": cards}
    return Built(
        title=title,
        markdown="\n".join(lines).strip(),
        primary=json.dumps(deck).encode(),
        primary_mime="application/json",
        primary_filename=f"{slug(title, 'flashcards')}.json",
    )
