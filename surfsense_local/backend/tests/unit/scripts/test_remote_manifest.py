"""The remote manifest is models.dev translated into the app's own words.

The fixture is a recorded subset of `https://models.dev/api.json`, so every
assertion here is about a real upstream entry.
"""

import json
from pathlib import Path

import pytest
from remote_manifest.endpoints import ENDPOINTS, Fixed, stale_endpoints
from remote_manifest.guard import shrinkage
from remote_manifest.render import render
from remote_manifest.translate import translate

from modules.llm.catalog.remote.manifest.schema import SCHEMA_VERSION, RemoteManifest

pytestmark = pytest.mark.unit

SAMPLE = Path(__file__).parents[2] / "fixtures" / "models_dev_sample.json"


@pytest.fixture
def api() -> dict:
    """A fresh copy per test, so a test that edits an entry cannot leak."""
    return json.loads(SAMPLE.read_text())


def test_models_stay_under_the_provider_that_serves_them(api: dict) -> None:
    """The same id means what each provider says it means, so nesting is kept."""
    manifest = translate(api)

    assert set(manifest["providers"]) == set(api)
    assert "gpt-5-5" in manifest["providers"]["kenari"]["models"]
    assert "gpt-5-5" in manifest["providers"]["neon"]["models"]


def test_a_model_keeps_its_evidence_and_display_fields_and_nothing_else(
    api: dict,
) -> None:
    """Cost, SDK names and environment variables have no reader in this app."""
    nano = translate(api)["providers"]["openai"]["models"]["gpt-5-nano"]

    assert nano == {
        "name": "GPT-5 Nano",
        "family": "gpt-nano",
        "description": api["openai"]["models"]["gpt-5-nano"]["description"],
        "release_date": "2025-08-07",
        "status": None,
        "modalities": {"input": ["text", "image"], "output": ["text"]},
        "context": 400000,
        "output_limit": 128000,
        "tool_call": True,
        "reasoning": True,
        "reasoning_options": [
            {"type": "effort", "values": ["minimal", "low", "medium", "high"]}
        ],
        "structured_output": True,
        "temperature": False,
        "call": None,
    }


def test_a_provider_keeps_its_name_and_doc_link(api: dict) -> None:
    """The row links to the provider's own page instead of showing a price."""
    openai = translate(api)["providers"]["openai"]

    assert {key: openai[key] for key in ("name", "doc")} == {
        "name": "OpenAI",
        "doc": "https://platform.openai.com/docs/models",
    }
    assert "npm" not in openai and "env" not in openai


def test_the_translation_is_what_the_app_loads(api: dict) -> None:
    """The script validates before writing, so it fails there, not at startup."""
    manifest = RemoteManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "source": "https://models.dev/api.json",
            "refreshed_at": "2026-09-23",
            **translate(api),
        }
    )

    assert manifest.providers["openai"].models["gpt-5-nano"].context == 400000


def test_a_zero_context_window_is_not_a_window_of_zero(api: dict) -> None:
    """136 entries say 0, all image or video models where a token window means
    nothing. Passing that to a budget would floor every prompt."""
    image = translate(api)["providers"]["openai"]["models"]["gpt-image-1"]

    assert api["openai"]["models"]["gpt-image-1"]["limit"]["context"] == 0
    assert image["context"] is None


def test_an_unrecorded_field_stays_unrecorded(api: dict) -> None:
    """Absent upstream is None here, never a default of false."""
    del api["openai"]["models"]["gpt-5-nano"]["structured_output"]

    nano = translate(api)["providers"]["openai"]["models"]["gpt-5-nano"]

    assert nano["structured_output"] is None


def test_a_refresh_that_loses_a_provider_or_a_fifth_of_its_models_is_refused(
    api: dict,
) -> None:
    """A bad upstream day must not become a shipped manifest nobody looked at."""
    previous = translate(api)
    trimmed = json.loads(json.dumps(api))
    del trimmed["neon"]
    trimmed["openai"]["models"] = {"gpt-5-nano": trimmed["openai"]["models"]["gpt-5-nano"]}

    problems = shrinkage(previous, translate(trimmed))

    assert any("neon" in problem for problem in problems)
    assert any("models" in problem for problem in problems)
    assert shrinkage(previous, translate(api)) == []


def test_each_model_is_one_line_so_a_refresh_diff_names_what_changed(
    api: dict,
) -> None:
    """Indenting every field made the file 5.3 MB and a diff unreadable."""
    manifest = {"schema_version": 1, "source": "s", "refreshed_at": "d", **translate(api)}

    text = render(manifest)

    assert json.loads(text) == manifest
    nano = [line for line in text.splitlines() if line.strip().startswith('"gpt-5-nano"')]
    assert len(nano) == 1
    assert '"context": 400000' in nano[0]


def _connect(api: dict, provider: str) -> dict:
    return translate(api)["providers"][provider]["connect"]


def test_a_hosted_provider_models_dev_gives_no_url_takes_the_reviewed_one(
    api: dict,
) -> None:
    """OpenAI's SDK has its URL built in, so models.dev never states it."""
    assert _connect(api, "openai") == {
        "status": "ready",
        "base_url": "https://api.openai.com/v1",
        "base_url_origin": "reviewed",
        "account_fields": [],
        "key": "required",
        "local": False,
        "reason": None,
    }


def test_a_url_models_dev_states_with_the_openai_protocol_is_used_as_is(
    api: dict,
) -> None:
    """The reviewed table fills gaps; it never overrides models.dev."""
    openrouter = _connect(api, "openrouter")

    assert (openrouter["status"], openrouter["base_url"], openrouter["base_url_origin"]) == (
        "ready",
        "https://openrouter.ai/api/v1",
        "models.dev",
    )


def test_a_url_that_speaks_another_protocol_is_unreachable_and_says_why(
    api: dict,
) -> None:
    """MiniMax states a URL, but it answers Anthropic's API, not OpenAI's."""
    minimax = _connect(api, "minimax")

    assert minimax["status"] == "unreachable"
    assert "Anthropic" in minimax["reason"]


def test_a_url_template_asks_for_its_variables(api: dict) -> None:
    """Databricks' URL is the user's own workspace host."""
    databricks = _connect(api, "databricks")

    assert databricks["status"] == "needs_account_details"
    assert databricks["base_url"] == "https://${DATABRICKS_HOST}/ai-gateway/mlflow/v1"
    assert databricks["account_fields"] == [
        {"name": "DATABRICKS_HOST", "label": "Databricks host"}
    ]


def test_a_provider_that_needs_more_than_a_key_is_unreachable_with_the_reviewed_reason(
    api: dict,
) -> None:
    """Bedrock signs requests with AWS credentials; a key cannot."""
    bedrock = _connect(api, "amazon-bedrock")

    assert (bedrock["status"], bedrock["reason"]) == (
        "unreachable",
        ENDPOINTS["amazon-bedrock"].reason,
    )


def test_a_provider_with_no_known_url_asks_the_user_for_one(api: dict) -> None:
    """Nothing is guessed: Azure's URL is not in models.dev or the table."""
    azure = _connect(api, "azure")

    assert (azure["status"], azure["base_url"]) == ("needs_url", None)


def test_a_loopback_server_needs_no_key_and_is_local(api: dict) -> None:
    """LM Studio on this machine: no key, and no egress question."""
    lmstudio = _connect(api, "lmstudio")

    assert (lmstudio["status"], lmstudio["key"], lmstudio["local"]) == (
        "ready",
        "none",
        True,
    )


def test_a_model_served_only_on_responses_says_so(api: dict) -> None:
    """The client speaks /chat/completions, so this one would fail on first use."""
    model = translate(api)["providers"]["neon"]["models"]["gpt-5-6-terra"]

    assert model["call"] == {"route": "responses"}


def test_a_model_served_through_another_protocol_says_which(api: dict) -> None:
    """A gateway can serve one model through Anthropic's API under an OpenAI URL."""
    model = translate(api)["providers"]["zenmux"]["models"]["minimax/minimax-m2.1"]

    assert model["call"] == {"protocol": "anthropic"}


def test_every_reviewed_url_is_https() -> None:
    """A reviewed URL is a hosted provider's; a local server is never in the table."""
    for provider, entry in ENDPOINTS.items():
        if isinstance(entry, Fixed):
            assert entry.base_url.startswith("https://"), provider


def test_a_reviewed_entry_whose_provider_left_models_dev_is_flagged(api: dict) -> None:
    """Dead entries would otherwise pile up unread."""
    del api["openai"]

    assert "openai" in stale_endpoints(api)
