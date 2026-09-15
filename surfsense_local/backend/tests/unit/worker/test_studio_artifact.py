import pytest

from worker.studio.shared.artifact import Source, fallback_title

pytestmark = pytest.mark.unit

SOURCES = [Source(1, "Saturn facts", ""), Source(2, "Titan", ""), Source(3, "Rhea", "")]


def test_the_prompt_names_the_artifact_when_there_is_one() -> None:
    """What the user asked for is the best name we have."""
    assert (
        fallback_title("  Compare the moons ", SOURCES, "Image") == "Compare the moons"
    )
    assert len(fallback_title("x" * 300, SOURCES, "Image")) == 200


def test_otherwise_the_sources_do_and_the_label_is_last() -> None:
    """One source: its title. Several: the first and a count. None: the format."""
    assert fallback_title(None, SOURCES[:1], "Image") == "Saturn facts"
    assert fallback_title("", SOURCES, "Image") == "Saturn facts and 2 more"
    assert fallback_title(None, [], "Image") == "Image"
