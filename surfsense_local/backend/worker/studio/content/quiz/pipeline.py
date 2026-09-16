import json

from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

OPTIONS = 4
_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "questions": [{"question": str, '
    f'"options": [str] (exactly {OPTIONS}, distinct), "answer": str (one of the '
    'options, verbatim), "explanation": str (why, in one or two sentences)}]}. '
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
        "Write a multiple-choice quiz from the sources below — each question "
        f"with {OPTIONS} options, the correct answer and a short explanation, "
        "using their facts only." + focus + " " + _SCHEMA
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Quiz"
    lines = [f"# {title}", ""]
    questions = []

    for item in as_list(spec.get("questions")):
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
