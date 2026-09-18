import json

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

# The frontier prompt leaves the count to the material, so the ceiling is kept here.
CARDS = 20


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    return build(
        generate.run_model(model, prompt(model.tier, user_prompt), sources), sources
    )


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(
        __package__, tier, focus=prompting.focus(user_prompt), ceiling=CARDS
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Flashcards"
    lines = [f"# {title}", ""]
    cards = []

    for card in as_list(spec.get("cards")):
        if len(cards) == CARDS:
            break
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
