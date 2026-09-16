import json

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

OPTIONS = 4
# The frontier prompt leaves the count to the material, so the ceiling is kept here.
QUESTIONS = 10


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    return build(
        generate.run_model(model, prompt(model.tier, user_prompt), sources), sources
    )


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(
        __package__,
        tier,
        focus=prompting.focus(user_prompt),
        options=OPTIONS,
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
        options = [text for text in map(as_text, as_list(item.get("options"))) if text]
        answer = as_text(item.get("answer"))
        # The viewer scores by index, so an answer that is not an option is unusable.
        if not question or len(options) != OPTIONS or answer not in options:
            continue
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

    quiz = {"schema_version": 1, "title": title, "questions": questions}
    return Built(
        title=title,
        markdown="\n".join(lines).strip(),
        primary=json.dumps(quiz).encode(),
        primary_mime="application/json",
        primary_filename=f"{slug(title, 'quiz')}.json",
    )
