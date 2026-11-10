"""Content kinds: the model writes markdown or JSON, the worker renders it as-is."""

import json
from types import SimpleNamespace

import pytest

from modules.llm.profile import Tier
from worker.studio.content.flashcards import pipeline as flashcards
from worker.studio.content.flashcards import schema as flashcards_schema
from worker.studio.content.mindmap import pipeline as mindmap
from worker.studio.content.quiz import pipeline as quiz
from worker.studio.content.quiz import schema as quiz_schema
from worker.studio.content.summary import pipeline as summary
from worker.studio.shared import generate
from worker.studio.shared.artifact import Source
from worker.studio.shared.text import parse_json

pytestmark = pytest.mark.unit


def test_a_quiz_is_asked_for_differently_depending_on_the_model() -> None:
    """A 3B model scores best on the shortest prompt, a frontier one on the fullest."""
    compact = quiz.prompt(Tier.COMPACT, None)
    capable = quiz.prompt(Tier.CAPABLE, None)
    frontier = quiz.prompt(Tier.FRONTIER, None)

    assert len({compact, capable, frontier}) == 3
    assert len(compact) < len(capable)


def test_a_quiz_carries_the_users_focus_and_its_own_numbers_at_every_tier() -> None:
    """A steer the user typed, or a count the builder enforces, must reach the model."""
    for tier in Tier:
        filled = quiz.prompt(tier, "  the 2031 rainfall figures  ")

        assert "Focus on: the 2031 rainfall figures" in filled
        assert f"exactly {quiz.DISTRACTORS}" in filled
        assert "$" not in filled


def test_a_quiz_is_capped_where_its_prompt_says_it_is() -> None:
    """Open counts are a prompt's request; the ceiling is the builder's contract."""
    raw = _quiz(40)

    built = quiz.build(raw, [])

    assert len(json.loads(built.primary)["questions"]) == quiz.QUESTIONS


def test_a_quiz_asks_the_model_for_its_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shape the builder reads is enforced while the model writes, so a
    small model cannot drift off it; the prompt still says it in prose."""
    sent = _asked(monkeypatch, _quiz(1))

    quiz.render(SimpleNamespace(tier=Tier.COMPACT), [], None)

    assert [schema for _, schema in sent] == [
        quiz_schema.reply(at_least=1, at_most=quiz.QUESTIONS)
    ]


def test_the_quiz_schema_asks_for_what_the_builder_keeps() -> None:
    """A question the builder would drop is one the grammar should not allow."""
    reply = quiz_schema.reply(at_least=3, at_most=quiz.QUESTIONS)
    questions = reply["properties"]["questions"]
    question = questions["items"]
    distractors = question["properties"]["distractors"]

    assert set(reply["required"]) == {"title", "questions"}
    assert set(question["required"]) == {
        "question",
        "correct",
        "distractors",
        "explanation",
    }
    assert distractors["minItems"] == distractors["maxItems"] == quiz.DISTRACTORS
    assert (questions["minItems"], questions["maxItems"]) == (3, quiz.QUESTIONS)


def test_a_deck_asks_the_model_for_its_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """A small model that drifts off the shape loses the whole deck, not a card."""
    sent = _asked(monkeypatch, _deck(1))

    flashcards.render(SimpleNamespace(tier=Tier.COMPACT), [], None)

    assert [schema for _, schema in sent] == [
        flashcards_schema.reply(at_least=1, at_most=flashcards.CARDS)
    ]


def test_the_deck_schema_asks_for_what_the_builder_keeps() -> None:
    """A card without both sides is dropped, so the grammar asks for both."""
    reply = flashcards_schema.reply(at_least=4, at_most=flashcards.CARDS)
    cards = reply["properties"]["cards"]

    assert set(reply["required"]) == {"title", "cards"}
    assert set(cards["items"]["required"]) == {"front", "back"}
    assert (cards["minItems"], cards["maxItems"]) == (4, flashcards.CARDS)


def test_every_content_kind_is_asked_for_in_its_own_words_at_every_tier() -> None:
    """One prompt per kind and tier: a wording that suits a quiz never reaches a deck."""
    asked = {
        module.prompt(tier, "the 2031 rainfall figures")
        for module in (quiz, flashcards, mindmap, summary)
        for tier in Tier
    }

    assert len(asked) == 12
    assert all("Focus on: the 2031 rainfall figures" in text for text in asked)
    assert not any("$" in text for text in asked)


def test_a_deck_and_a_map_are_capped_where_their_prompts_say_they_are() -> None:
    """Open counts are a prompt's request; the ceiling is the builder's contract."""
    deck = flashcards.build(_deck(40), [])

    map_body = mindmap.build("# T\n" + "- Branch\n  - Leaf\n" * 40, []).markdown

    assert len(json.loads(deck.primary)["cards"]) == flashcards.CARDS
    assert map_body.count("\n- ") == mindmap.BRANCHES


def test_a_markdown_document_takes_its_title_from_the_first_h1() -> None:
    """The document title comes from the model's H1, so the list reads well."""
    built = summary.build("# Saturn's rings\n\nThey are mostly ice.", [])

    assert built.title == "Saturn's rings"
    assert built.markdown.startswith("# Saturn's rings")


def test_a_markdown_document_is_kept_as_a_file_to_download() -> None:
    """The body is also the primary file, so the panel offers it as a .md."""
    built = summary.build("# Saturn's rings\n\nThey are mostly ice.", [])

    assert built.primary == built.markdown.encode()
    assert built.primary_mime == "text/markdown"
    assert built.primary_filename == "saturn-s-rings.md"


def test_a_markdown_document_without_a_heading_still_has_a_title() -> None:
    """A model that skips the H1 still yields a named, openable artifact."""
    built = summary.build("Just prose, no heading.", [])

    assert built.title == "Markdown"
    assert built.primary_filename == "markdown.md"


def test_parse_json_survives_fences_and_surrounding_prose() -> None:
    """Local models wrap JSON in prose and fences; the object is still recovered."""
    raw = 'Sure!\n```json\n{"title": "T", "sections": []}\n```\nHope that helps.'
    assert parse_json(raw) == {"title": "T", "sections": []}


def test_parse_json_rejects_a_non_object() -> None:
    """A builder must fail loudly, not render half a spec, on bad output."""
    with pytest.raises(ValueError, match="JSON"):
        parse_json("not json at all")


def test_mindmap_renders_a_nested_outline_and_no_file() -> None:
    """A mind map is a markdown body Markmap reads; there is nothing to download."""
    built = mindmap.build("# Saturn\n- Rings\n  - Ice", [])

    assert built.primary is None
    assert "# Saturn" in built.markdown
    assert "- Rings" in built.markdown
    assert "  - Ice" in built.markdown


def test_flashcards_and_quiz_project_to_readable_markdown() -> None:
    """The searchable body carries the content, so both index and read plainly."""
    cards = flashcards.build(
        '{"title": "Deck", "cards": [{"front": "Q?", "back": "A."}]}', []
    )
    assert cards.primary_mime == "application/json"
    assert "Q?" in cards.markdown and "A." in cards.markdown

    test = quiz.build(
        '{"title": "Test", "questions": [{"question": "Q?", '
        '"correct": "a", "distractors": ["b", "c", "d"]}]}',
        [],
    )
    assert "Q?" in test.markdown and "Answer: a" in test.markdown


def _asked(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[tuple[str, dict]]:
    """Every system prompt and schema a pipeline sends, each answered with `reply`."""
    sent: list[tuple[str, dict]] = []

    def fake_run_model(_model: object, system: str, *_a: object, **kw: object) -> str:
        sent.append((system, kw["json_schema"]))
        return reply

    monkeypatch.setattr(generate, "run_model", fake_run_model)
    return sent


def _source(chars: int) -> list[Source]:
    return [Source(1, "Notes", "x" * chars)]


def _deck(count: int) -> str:
    cards = [{"front": f"Q{n}?", "back": "A."} for n in range(count)]
    return json.dumps({"title": "T", "cards": cards})


def _quiz(count: int) -> str:
    questions = [
        {
            "question": f"Q{n}?",
            "correct": "right",
            "distractors": ["w1", "w2", "w3"],
            "explanation": "E.",
        }
        for n in range(count)
    ]
    return json.dumps({"title": "T", "questions": questions})


# The sources' room at the 8,192-token window a local model loads at, in characters.
SMALLEST_WINDOW_CHARS = 12_276


def test_a_small_model_is_held_to_as_many_cards_as_its_sources_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A small model left to stop on its own closed a deck after one card."""
    sent = _asked(monkeypatch, _deck(5))
    sources = _source(5 * flashcards.CHARS_PER_CARD)

    flashcards.render(SimpleNamespace(tier=Tier.COMPACT), sources, None)

    system, schema = sent[0]
    assert "Make 5 study flashcards" in system
    assert schema["properties"]["cards"]["minItems"] == 5


def test_a_small_model_given_the_smallest_window_is_asked_for_a_full_deck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At the 8,192-token window a local model loads at, the sources carry all 20."""
    sent = _asked(monkeypatch, _deck(flashcards.CARDS))

    flashcards.render(
        SimpleNamespace(tier=Tier.COMPACT), _source(SMALLEST_WINDOW_CHARS), None
    )

    system, schema = sent[0]
    assert f"Make {flashcards.CARDS} study flashcards" in system
    assert schema["properties"]["cards"]["minItems"] == flashcards.CARDS


def test_a_larger_model_still_chooses_how_many_cards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the small prompt states a count; a larger model is never padded to one."""
    for tier in (Tier.CAPABLE, Tier.FRONTIER):
        sent = _asked(monkeypatch, _deck(3))

        flashcards.render(SimpleNamespace(tier=tier), _source(50_000), None)

        assert sent[0][1]["properties"]["cards"]["minItems"] == 1


def test_a_small_model_is_held_to_as_many_questions_as_its_sources_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The quiz takes the deck's rule: a stated count the grammar holds."""
    sent = _asked(monkeypatch, _quiz(quiz.QUESTIONS))

    quiz.render(
        SimpleNamespace(tier=Tier.COMPACT), _source(SMALLEST_WINDOW_CHARS), None
    )

    system, schema = sent[0]
    assert f"quiz of {quiz.QUESTIONS} questions" in system
    assert schema["properties"]["questions"]["minItems"] == quiz.QUESTIONS


def test_a_repeated_card_is_kept_once() -> None:
    """A small model writes the same front twice; it is one card."""
    raw = json.dumps(
        {
            "title": "T",
            "cards": [
                {"front": "What is ATP?", "back": "Energy."},
                {"front": "what is  ATP?", "back": "Energy again."},
            ],
        }
    )

    assert len(json.loads(flashcards.build(raw, []).primary)["cards"]) == 1


def test_a_deck_with_no_usable_card_fails_rather_than_opening_empty() -> None:
    """An empty deck opened as ready; failing says why and lets the job try again."""
    with pytest.raises(ValueError, match="no usable cards"):
        flashcards.build('{"title": "T", "cards": [{"front": "Q?", "back": ""}]}', [])


def test_a_card_whose_back_repeats_its_front_is_dropped() -> None:
    """Qwen3 0.6B copied one source sentence onto both sides of 9 to 19 cards in
    3 decks of 12; such a card asks nothing."""
    sentence = (
        "The transformer was proposed in the 2017 paper Attention Is All You Need"
    )
    raw = json.dumps(
        {
            "title": "T",
            "cards": [
                {"front": sentence, "back": sentence},
                {"front": f"{sentence}.", "back": f"{sentence.lower()}!"},
                {"front": "When was the transformer proposed?", "back": "In 2017."},
            ],
        }
    )

    cards = json.loads(flashcards.build(raw, []).primary)["cards"]

    assert [card["front_text"] for card in cards] == [
        "When was the transformer proposed?"
    ]


def test_a_quiz_question_offers_its_answer_among_the_distractors() -> None:
    """The answer is a field of its own, so it cannot fail to match an option."""
    built = quiz.build(_quiz(1), [])
    question = json.loads(built.primary)["questions"][0]

    assert sorted(question["options"]) == ["right", "w1", "w2", "w3"]
    assert question["options"][question["correct_option_index"]] == "right"
    assert "Answer: right" in built.markdown


def test_the_answer_is_not_always_in_the_same_place() -> None:
    """The model writes the answer first, so the builder moves it."""
    questions = json.loads(quiz.build(_quiz(quiz.QUESTIONS), []).primary)["questions"]

    assert len({q["correct_option_index"] for q in questions}) > 1


def test_a_question_is_shuffled_the_same_way_every_time() -> None:
    """A regenerate that writes the same question keeps its options in place."""
    assert quiz.build(_quiz(3), []).primary == quiz.build(_quiz(3), []).primary


def test_a_question_whose_options_repeat_is_dropped() -> None:
    """A small model wrote four identical options, which cannot be answered."""
    raw = json.dumps(
        {
            "title": "T",
            "questions": [
                {
                    "question": "Q?",
                    "correct": "Same",
                    "distractors": ["same", "b", "c"],
                },
                {"question": "R?", "correct": "a", "distractors": ["b", "c", "d"]},
            ],
        }
    )

    kept = json.loads(quiz.build(raw, []).primary)["questions"]

    assert [q["question_text"] for q in kept] == ["R?"]


def test_a_quiz_with_no_usable_question_fails_rather_than_opening_empty() -> None:
    """An empty quiz opened as ready; failing says why and lets the job try again."""
    with pytest.raises(ValueError, match="no usable questions"):
        quiz.build('{"title": "T", "questions": []}', [])


def test_a_map_is_written_free_and_its_reply_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No schema: the model chooses the map's shape. A JSON map broke on a 4B
    model in 9 of 9, and a schema that allows any depth crashed llama-server."""
    sent: list[dict] = []

    def fake_run_model(*_a: object, **kw: object) -> str:
        sent.append(kw)
        return "# T\n- A"

    monkeypatch.setattr(generate, "run_model", fake_run_model)

    mindmap.render(SimpleNamespace(tier=Tier.COMPACT), [], None)

    assert sent[0].get("json_schema") is None
    assert sent[0]["max_tokens"] == mindmap.REPLY_TOKENS


def test_a_map_keeps_whatever_depth_the_model_writes() -> None:
    """Depth is the model's to choose; nothing flattens a deep branch."""
    raw = "# T\n- a\n  - b\n    - c\n      - d\n        - e\n          - f"

    body = mindmap.build(raw, []).markdown

    assert "          - f" in body


def test_a_map_evens_out_how_the_model_indented_and_bulleted() -> None:
    """Four spaces, a tab, `*` and numbers all mean one level down."""
    raw = "```markdown\n# T\n* a\n    1. b\n\t\t- c\n* d\n```"

    body = mindmap.build(raw, []).markdown

    assert body == "# T\n- a\n  - b\n    - c\n- d"


def test_a_map_reads_headings_as_branches() -> None:
    """Some models write each branch as a heading with its bullets beneath."""
    body = mindmap.build(
        "# T\n## Causes\n- Debt\n  - War loans\n## Results", []
    ).markdown

    assert body == "# T\n- Causes\n  - Debt\n    - War loans\n- Results"


def test_a_map_drops_prose_around_the_outline() -> None:
    """Small models add a sentence before or after; only the outline is kept."""
    body = mindmap.build("Here is your map:\n# T\n- a\nHope it helps!", []).markdown

    assert body == "# T\n- a"


def test_a_label_loses_the_markup_wrapped_around_it() -> None:
    """Qwen3 0.6B wrote its branches as `**# Causes**`."""
    body = mindmap.build("# T\n- **# Causes**\n  - __Debt__\n  - War **loans**", [])

    assert body.markdown == "# T\n- Causes\n  - Debt\n  - War **loans**"


def test_a_run_on_list_under_one_label_is_cut() -> None:
    """One 4B map hung 300 labels under one branch until its reply ran out."""
    raw = "# T\n- a\n" + "".join(f"  - leaf {n}\n" for n in range(40))

    body = mindmap.build(raw, []).markdown

    assert body.count("\n  - ") == mindmap.CHILDREN


def test_a_map_with_no_branch_fails_rather_than_opening_empty() -> None:
    """A map of a title alone shows nothing; failing says why."""
    with pytest.raises(ValueError, match="no usable branches"):
        mindmap.build("# T\nNothing to map.", [])
