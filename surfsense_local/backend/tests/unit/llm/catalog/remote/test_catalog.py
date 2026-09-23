"""The remote catalog: the manifest and the user's connections, as rows."""

import pytest

from modules.llm.catalog.remote.catalog import connection_rows, provider_rows, providers
from modules.llm.catalog.remote.rows import Availability, ConnectionInfo, ListedModel
from modules.llm.catalog.source import Source
from modules.llm.model_type import ModelType

from .conftest import PAINTER, connect, model

pytestmark = pytest.mark.unit

WORK = ConnectionInfo(id=1, label="OpenAI (work)", catalog_provider="openai")
HOME = ConnectionInfo(id=2, label="OpenAI (home)", catalog_provider="openai")
GATEWAY = ConnectionInfo(id=3, label="Gateway", catalog_provider="custom")


@pytest.fixture
def lookup(lookup_of):
    """OpenAI (chat and image), Bedrock (unreachable), Neon (a /responses-only model)."""
    return lookup_of(
        {
            "openai": {"models": {"gpt-5": model(), "gpt-image-1": model(PAINTER)}},
            "amazon-bedrock": {
                "connect": connect("unreachable", "Signs requests with AWS credentials"),
                "models": {"claude": model()},
            },
            "neon": {
                "models": {"gpt-5-pro": model(call={"route": "responses"})},
            },
        }
    )


def _by_model(rows):
    return {row.model_id: row for row in rows}


def test_providers_say_how_many_models_of_each_type_they_serve(lookup) -> None:
    """Enough to list providers without sending thousands of rows."""
    summary = {p.id: p for p in providers(lookup, connected={"openai": 2})}

    assert summary["openai"].type_counts == {ModelType.TEXT_GEN: 1, ModelType.IMAGE_GEN: 1}
    assert summary["openai"].connections == 2
    assert summary["amazon-bedrock"].connect.status == "unreachable"


def test_a_provider_nobody_connected_offers_its_models_to_add_a_key(lookup) -> None:
    """Browsable before connecting; the row says a key is what is missing."""
    rows = provider_rows(lookup, "openai", connections=[])

    gpt = _by_model(rows)["gpt-5"]
    assert (gpt.source, gpt.availability, gpt.connection) == (
        Source.REMOTE,
        Availability.NOT_CONNECTED,
        None,
    )
    assert gpt.types == {ModelType.TEXT_GEN}


def test_each_connection_to_a_provider_gets_its_own_unchecked_rows(lookup) -> None:
    """Two keys can reach different models, so neither speaks for the other."""
    rows = provider_rows(lookup, "openai", connections=[WORK, HOME])

    gpt = [row for row in rows if row.model_id == "gpt-5"]
    assert {row.connection.label for row in gpt} == {"OpenAI (work)", "OpenAI (home)"}
    assert {row.availability for row in gpt} == {Availability.UNCHECKED}


def test_an_unreachable_provider_says_why_and_offers_no_slot(lookup) -> None:
    """A model that cannot be called must not be selectable anywhere."""
    claude = _by_model(provider_rows(lookup, "amazon-bedrock", connections=[]))["claude"]

    assert claude.availability is Availability.UNUSABLE
    assert claude.reason == "Signs requests with AWS credentials"
    assert claude.selectable_for == ()


def test_a_responses_only_model_is_unusable_and_says_so(lookup) -> None:
    """The client speaks /chat/completions; this model would fail on first use."""
    pro = _by_model(provider_rows(lookup, "neon", connections=[]))["gpt-5-pro"]

    assert pro.availability is Availability.UNUSABLE
    assert "/responses" in pro.reason


def test_a_connection_marks_what_its_listing_serves_and_what_it_does_not(lookup) -> None:
    """A retired model, or one the key cannot reach, is not served."""
    rows = _by_model(
        connection_rows(lookup, WORK, listing=[ListedModel("gpt-5", (), known=False)])
    )

    assert rows["gpt-5"].availability is Availability.AVAILABLE
    assert rows["gpt-image-1"].availability is Availability.NOT_SERVED


def test_a_listed_model_newer_than_the_manifest_is_added_as_listed(lookup) -> None:
    """The live listing is ahead of a manifest refreshed a few times a year."""
    listed = ListedModel("gpt-7", (ModelType.TEXT_GEN,), known=True)

    gpt_7 = _by_model(connection_rows(lookup, WORK, listing=[listed]))["gpt-7"]

    assert (gpt_7.availability, gpt_7.types) == (
        Availability.AVAILABLE,
        {ModelType.TEXT_GEN},
    )


def test_a_failed_listing_leaves_the_manifest_rows_unchecked_not_gone(lookup) -> None:
    """An endpoint being down is not the models disappearing."""
    rows = connection_rows(lookup, WORK, listing=None)

    assert {row.availability for row in rows} == {Availability.COULD_NOT_CHECK}
    assert {row.model_id for row in rows} == {"gpt-5", "gpt-image-1"}


def test_a_custom_connection_shows_only_what_it_lists(lookup) -> None:
    """A company gateway is in no manifest; its listing is the whole truth."""
    rows = connection_rows(
        lookup, GATEWAY, listing=[ListedModel("acme/llama-support", (), known=False)]
    )

    assert [(row.model_id, row.known, row.availability) for row in rows] == [
        ("acme/llama-support", False, Availability.AVAILABLE)
    ]
    assert len(rows[0].selectable_for) == len(ModelType)
