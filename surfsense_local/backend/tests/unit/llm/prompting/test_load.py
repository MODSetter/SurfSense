from collections.abc import Callable
from importlib import invalidate_caches
from pathlib import Path

import pytest

from modules.llm.profile import Tier
from modules.llm.prompting import load

pytestmark = pytest.mark.unit


@pytest.fixture
def ship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Callable[..., str]:
    """Stand up a package shipping prompts, which is all the loader reads."""
    name = f"case_{abs(hash(request.node.name)):x}"
    (tmp_path / name / "prompts").mkdir(parents=True)
    (tmp_path / name / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(tmp_path)
    invalidate_caches()

    def write(tier: Tier, text: str, case: str = "") -> str:
        folder = tmp_path / name / "prompts" / case
        folder.mkdir(exist_ok=True)
        (folder / f"{tier}.md").write_text(text)
        return name

    return write


def test_the_tier_names_the_file_a_case_loads(
    ship: Callable[..., str],
) -> None:
    """One file is the whole prompt for a case and tier; nothing is composed."""
    package = ship(Tier.COMPACT, "Write a quiz from the sources.\n")

    assert load(package, Tier.COMPACT) == "Write a quiz from the sources."


def test_a_slot_is_filled_and_a_schema_is_left_alone(
    ship: Callable[..., str],
) -> None:
    """Every prompt ends in a JSON schema, so braces reach the model as written."""
    package = ship(
        Tier.CAPABLE, 'Write a quiz. $focus\nReturn only JSON: {"title": str}'
    )

    filled = load(package, Tier.CAPABLE, focus="Focus on rainfall.")

    assert (
        filled == 'Write a quiz. Focus on rainfall.\nReturn only JSON: {"title": str}'
    )


def test_two_cases_in_one_package_keep_their_own_prompts(
    ship: Callable[..., str],
) -> None:
    """A podcast plans an episode and scripts it: one package, two jobs, two prompts."""
    package = ship(Tier.COMPACT, "Plan the episode.", case="outline")
    ship(Tier.COMPACT, "Script the segment.", case="draft")

    assert load(package, Tier.COMPACT, case="outline") == "Plan the episode."
    assert load(package, Tier.COMPACT, case="draft") == "Script the segment."


def test_an_unfilled_slot_never_reaches_the_model(
    ship: Callable[..., str],
) -> None:
    """A raw $slot in an artifact is worse than a job that fails and says why."""
    package = ship(Tier.FRONTIER, "Write a quiz. $focus")

    with pytest.raises(ValueError, match=r"frontier.*focus"):
        load(package, Tier.FRONTIER)
