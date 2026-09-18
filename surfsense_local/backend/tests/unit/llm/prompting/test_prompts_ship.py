"""Every case that ships prompts ships all three, or a model is handed nothing."""

from pathlib import Path

import pytest

from modules.artifacts.podcast.brief import Duration, PodcastBrief, Speaker, Style
from modules.llm.profile import Tier
from modules.llm.prompting import load
from worker.studio.content.flashcards import pipeline as flashcards
from worker.studio.content.mindmap import pipeline as mindmap
from worker.studio.content.quiz import pipeline as quiz
from worker.studio.content.summary import pipeline as summary
from worker.studio.media.audio.podcast import draft, outline
from worker.studio.media.audio.podcast.outline import Segment
from worker.studio.media.visual.image import pipeline as image
from worker.studio.media.visual.infographic import pipeline as infographic
from worker.studio.office import prompt as office
from worker.studio.office.docx import docx
from worker.studio.office.pdf import pdf
from worker.studio.office.pptx import pptx
from worker.studio.office.xlsx import xlsx
from worker.studio.web.html import pipeline as html

pytestmark = pytest.mark.unit

BACKEND = Path(__file__).resolve().parents[4]
CASES = sorted(
    {
        prompt.parent
        for root in (BACKEND / "worker" / "studio", BACKEND / "modules" / "chat")
        for prompt in root.glob("**/prompts/**/*.md")
    }
)


def test_the_cases_are_found_where_they_ship() -> None:
    """A walker that finds nothing would pass every assertion below it."""
    assert CASES


@pytest.mark.parametrize(
    "case", CASES, ids=lambda folder: str(folder.relative_to(BACKEND))
)
def test_a_case_ships_a_prompt_for_every_tier(case: Path) -> None:
    """A missing file fails the job on the user's machine, where nobody can fix it."""
    for tier in Tier:
        assert (case / f"{tier}.md").read_text(encoding="utf-8").strip()


BRIEF = PodcastBrief(
    language="en",
    style=Style.INTERVIEW,
    duration=Duration.STANDARD,
    speakers=[Speaker(name="Sam", role="host", voice="pm_alex")],
)
SEGMENT = Segment("Rings", ["Galileo, 1610"], 300)
FOCUS = "the 2031 figures"


def _every_prompt(tier: Tier) -> dict[str, str]:
    """What each case sends the model at one tier, built the way it builds it."""
    return {
        "chat": load("modules.chat", tier),
        "quiz": quiz.prompt(tier, FOCUS),
        "flashcards": flashcards.prompt(tier, FOCUS),
        "mindmap": mindmap.prompt(tier, FOCUS),
        "summary": summary.prompt(tier, FOCUS),
        "html": html.prompt(tier, FOCUS),
        "image": image.prompt(tier, FOCUS),
        "infographic": infographic.prompt(tier, FOCUS),
        "outline": outline.prompt(tier, BRIEF, FOCUS),
        "draft": draft.prompt(tier, BRIEF, SEGMENT, 1, 2, "Sam: Welcome."),
    } | {spec.key: office.build(tier, spec, FOCUS) for spec in (docx, pptx, xlsx, pdf)}


@pytest.mark.parametrize("tier", list(Tier))
def test_every_case_renders_what_it_sends_the_model(tier: Tier) -> None:
    """A slot a file declares and its builder never fills is a `$focus` in a quiz."""
    for case, text in _every_prompt(tier).items():
        assert text.strip(), case
        assert "$" not in text, case
