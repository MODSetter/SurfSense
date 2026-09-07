from worker.studio.builders.types import Builder, Built, Source
from worker.studio.builders.util import as_list, as_text, parse_json

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "questions": '
    '[{"question": str, "options": [str], "answer": str}]}.'
)


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Focus on: {user_prompt}." if user_prompt else ""
    return (
        "Write a multiple-choice quiz from the sources below — each question "
        "with a few options and the correct answer, using their facts only."
        + focus
        + " "
        + _SCHEMA
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Quiz"
    lines = [f"# {title}", ""]

    for index, item in enumerate(as_list(spec.get("questions")), start=1):
        if not isinstance(item, dict):
            continue
        question = as_text(item.get("question"))
        if not question:
            continue
        lines.append(f"**{index}. {question}**")
        lines.append("")
        for option in as_list(item.get("options")):
            text = as_text(option)
            if text:
                lines.append(f"- {text}")
        answer = as_text(item.get("answer"))
        if answer:
            lines.append(f"\n_Answer: {answer}_")
        lines.append("")

    return Built(title=title, markdown="\n".join(lines).strip())


quiz = Builder(key="quiz", prompt=prompt, build=build)
