import json
import random

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.content import study_count
from worker.studio.content.quiz.schema import DISTRACTORS, OPTIONS, reply
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

# The frontier prompt leaves the count to the material, so the ceiling is kept here.
QUESTIONS = 10
# At the 8,192-token window a local model loads at, the sources hold about
# 12,000 characters: a full quiz. A question averaged 380 characters from
# Qwen3 4B, so 10 fit the reply's quarter of that window.
CHARS_PER_QUESTION = 1_200

NO_QUESTIONS = (
    "The model wrote no usable questions. Try again, or choose a larger model."
)

__all__ = ["DISTRACTORS", "OPTIONS", "QUESTIONS", "build", "prompt", "render"]


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    count = study_count.asked_count(sources, QUESTIONS, CHARS_PER_QUESTION)
    schema = reply(
        at_least=study_count.least_count(model.tier, count), at_most=QUESTIONS
    )
    raw = generate.run_model(
        model, prompt(model.tier, user_prompt, count), sources, json_schema=schema
    )
    return build(raw, sources)


def prompt(tier: Tier, user_prompt: str | None, count: int = QUESTIONS) -> str:
    return prompting.load(
        __package__,
        tier,
        focus=prompting.focus(user_prompt),
        distractors=DISTRACTORS,
        count=count,
        ceiling=QUESTIONS,
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Quiz"
    lines = [f"# {title}", ""]
    questions = []

    for item in as_list(spec.get("questions")):
        if len(questions) == QUESTIONS:
            break
        if not isinstance(item, dict):
            continue
        question = as_text(item.get("question"))
        answer = as_text(item.get("correct"))
        options = [answer, *map(as_text, as_list(item.get("distractors")))]
        distinct = {" ".join(option.casefold().split()) for option in options}
        # Exactly OPTIONS, all distinct and none blank: an unconstrained reply
        # can carry more distractors than the schema allows.
        if (
            not question
            or len(options) != OPTIONS
            or len(distinct) != OPTIONS
            or "" in distinct
        ):
            continue
        # Seeded by the question, so the same question keeps its order.
        random.Random(question).shuffle(options)
        questions.append(
            {
                "question_text": question,
                "options": options,
                "correct_option_index": options.index(answer),
                "explanation_text": as_text(item.get("explanation")),
            }
        )
        lines.append(f"**{len(questions)}. {question}**")
        lines.append("")
        lines += [f"- {option}" for option in options]
        lines += [f"\n_Answer: {answer}_", ""]

    if not questions:
        raise ValueError(NO_QUESTIONS)
    quiz = {"schema_version": 1, "title": title, "questions": questions}
    return Built(
        title=title,
        markdown="\n".join(lines).strip(),
        primary=json.dumps(quiz).encode(),
        primary_mime="application/json",
        primary_filename=f"{slug(title, 'quiz')}.json",
    )
