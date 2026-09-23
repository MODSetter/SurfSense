"""The remote manifest is models.dev translated into the app's own words.

The fixture is a recorded subset of `https://models.dev/api.json`, so every
assertion here is about a real upstream entry.
"""

import json
from pathlib import Path

import pytest
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
