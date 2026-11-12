import json
import re
from difflib import SequenceMatcher

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.content import study_count
from worker.studio.content.flashcards.schema import reply
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

# The frontier prompt leaves the count to the material, so the ceiling is kept here.
CARDS = 20
# At the 8,192-token window a local model loads at, the sources hold about
# 12,000 characters: a full deck. A card averaged 230 characters from Qwen3 4B,
# so 20 fit the reply's quarter of that window.
CHARS_PER_CARD = 600

NO_CARDS = "The model wrote no usable cards. Try again, or choose a larger model."

# How alike a card's two sides may be. At this mark Qwen3 0.6B's copied cards
# were caught, and no card from Qwen3 4B or Gemma 3 4B in 24 decks.
SAME_SIDES = 0.9
_WORDS = re.compile(r"\w+")


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    count = study_count.asked_count(sources, CARDS, CHARS_PER_CARD)
    schema = reply(at_least=study_count.least_count(model.tier, count), at_most=CARDS)
    raw = generate.run_model(
        model, prompt(model.tier, user_prompt, count), sources, json_schema=schema
    )
    return build(raw, sources)


def prompt(tier: Tier, user_prompt: str | None, count: int = CARDS) -> str:
    return prompting.load(
        __package__,
        tier,
        focus=prompting.focus(user_prompt),
        count=count,
        ceiling=CARDS,
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Flashcards"
    lines = [f"# {title}", ""]
    cards = []
    fronts: set[str] = set()

    for card in as_list(spec.get("cards")):
        if len(cards) == CARDS:
            break
        if not isinstance(card, dict):
            continue
        front = as_text(card.get("front"))
        back = as_text(card.get("back"))
        seen = " ".join(front.casefold().split())
        if front and back and seen not in fronts and not _repeats(front, back):
            fronts.add(seen)
            cards.append({"front_text": front, "back_text": back})
            lines += [f"**{len(cards)}. {front}**", "", back, ""]

    if not cards:
        raise ValueError(NO_CARDS)
    deck = {"schema_version": 1, "title": title, "cards": cards}
    return Built(
        title=title,
        markdown="\n".join(lines).strip(),
        primary=json.dumps(deck).encode(),
        primary_mime="application/json",
        primary_filename=f"{slug(title, 'flashcards')}.json",
    )


def _repeats(front: str, back: str) -> bool:
    """A back that says what the front says, but for case and punctuation, asks nothing."""
    words = [" ".join(_WORDS.findall(side.casefold())) for side in (front, back)]
    return SequenceMatcher(None, *words).ratio() >= SAME_SIDES
