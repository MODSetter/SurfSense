import json
from pathlib import Path

import pytest

from surfsense_plugin_manifest import ManifestError, load_manifest

pytestmark = pytest.mark.unit


def _hn_search() -> dict:
    """A small, valid manifest that each test changes one thing in."""
    return {
        "id": "hn-search",
        "name": "Hacker News search",
        "description": "Adds matching stories as notes.",
        "author": "Alice",
        "access": "free",
        "hosts": ["hn.algolia.com"],
        "actions": [
            {
                "name": "search",
                "title": "Search Hacker News",
                "inputs": [
                    {
                        "name": "query",
                        "title": "Search for",
                        "kind": "string",
                        "required": True,
                    }
                ],
            }
        ],
    }


def _write(folder: Path, manifest: dict) -> Path:
    """Writes the manifest where load_manifest reads it."""
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_a_valid_manifest_loads_with_its_fields(tmp_path: Path) -> None:
    """What a plugin declares is readable from the loaded manifest."""
    manifest = load_manifest(_write(tmp_path, _hn_search()))

    assert manifest.id == "hn-search"
    assert manifest.access == "free"
    assert manifest.hosts == ["hn.algolia.com"]
    assert manifest.actions[0].name == "search"
    assert manifest.actions[0].inputs[0].kind == "string"
    assert manifest.actions[0].inputs[0].required is True


def test_what_an_action_leaves_out_takes_its_default(tmp_path: Path) -> None:
    """No timeout means 30 minutes, and an input is optional unless it says so."""
    declared = _hn_search()
    del declared["actions"][0]["inputs"][0]["required"]

    action = load_manifest(_write(tmp_path, declared)).actions[0]

    assert action.timeout_seconds == 1800
    assert action.inputs[0].required is False


def test_a_field_this_version_does_not_know_is_ignored(tmp_path: Path) -> None:
    """A manifest written for a newer app still loads in an older one."""
    declared = _hn_search()
    declared["icon"] = "icon.png"
    declared["actions"][0]["schedule"] = "daily"

    assert load_manifest(_write(tmp_path, declared)).id == "hn-search"


@pytest.mark.parametrize(
    ("stamped", "version"), [({}, None), ({"version": "2.4.0"}, "2.4.0")]
)
def test_the_version_is_the_one_a_release_stamped(
    tmp_path: Path, stamped: dict, version: str | None
) -> None:
    """A downloaded copy carries its release's version; the repository's has none."""
    declared = _hn_search() | stamped

    assert load_manifest(_write(tmp_path, declared)).version == version


def _errors_in(folder: Path, manifest: dict) -> list[str]:
    """The errors a refused manifest reports, for a test to compare whole."""
    with pytest.raises(ManifestError) as refused:
        load_manifest(_write(folder, manifest))
    return refused.value.errors


SAFE_IN_URLS = (
    'must be lowercase letters, digits and "-", start with a letter, and be at most'
    " 64 characters, so it is safe in file names and URLs"
)
VALID_VARIABLE = (
    'must be lowercase letters, digits and "_", start with a letter, and be at most'
    " 64 characters, so it is a valid Python argument and environment variable name"
)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("id", "HN-Search", f"id: {SAFE_IN_URLS}"),
        ("name", "", "name: must be 1 to 80 characters"),
        ("description", "x" * 201, "description: must be 1 to 200 characters"),
    ],
)
def test_a_badly_formed_identity_is_refused(
    tmp_path: Path, field: str, value: str, error: str
) -> None:
    """The id, name and description a store and a list can show are well formed."""
    declared = _hn_search()
    declared[field] = value

    assert _errors_in(tmp_path, declared) == [error]


def test_access_is_free_or_paid(tmp_path: Path) -> None:
    """There is no third kind of access, and no price."""
    declared = _hn_search()
    declared["access"] = "premium"

    assert _errors_in(tmp_path, declared) == ["access: must be free or paid"]


NOT_A_BARE_HOSTNAME = (
    "hosts[0]: must be a lowercase hostname alone: no scheme, port, path or wildcard"
)
LOOPBACK = "hosts[0]: loopback is the app itself, not egress, so it is not a host"


@pytest.mark.parametrize(
    ("host", "error"),
    [
        ("https://hn.algolia.com", NOT_A_BARE_HOSTNAME),
        ("hn.algolia.com:443", NOT_A_BARE_HOSTNAME),
        ("hn.algolia.com/api", NOT_A_BARE_HOSTNAME),
        ("*.algolia.com", NOT_A_BARE_HOSTNAME),
        ("HN.Algolia.com", NOT_A_BARE_HOSTNAME),
        ("localhost", LOOPBACK),
        ("api.localhost", LOOPBACK),
        ("127.0.0.1", LOOPBACK),
        ("::1", LOOPBACK),
    ],
)
def test_a_host_is_exactly_what_the_user_consents_to(
    tmp_path: Path, host: str, error: str
) -> None:
    """Each host is the one name the egress prompt shows and the grant matches."""
    declared = _hn_search()
    declared["hosts"] = [host]

    assert _errors_in(tmp_path, declared) == [error]


@pytest.mark.parametrize("host", ["hn.algolia.com", "93.184.216.34"])
def test_a_bare_hostname_or_address_is_a_host(tmp_path: Path, host: str) -> None:
    """A plain hostname, or an address that is not loopback, is accepted."""
    declared = _hn_search()
    declared["hosts"] = [host]

    assert load_manifest(_write(tmp_path, declared)).hosts == [host]


@pytest.mark.parametrize(
    ("secret", "error"),
    [
        ({"name": "token"}, "secrets[0].title: is required"),
        (
            {"name": "api-token", "title": "API token"},
            f"secrets[0].name: {VALID_VARIABLE}",
        ),
    ],
)
def test_a_secret_has_a_title_and_a_name_that_can_be_a_variable(
    tmp_path: Path, secret: dict, error: str
) -> None:
    """A secret is labelled for the user and handed over as an environment variable."""
    declared = _hn_search()
    declared["secrets"] = [secret]

    assert _errors_in(tmp_path, declared) == [error]


def _no_actions(declared: dict) -> None:
    """A plugin with nothing the app could run."""
    declared["actions"] = []


def _two_actions_named_alike(declared: dict) -> None:
    """Two actions the app could not tell apart."""
    declared["actions"].append(dict(declared["actions"][0]))


def _two_inputs_named_alike(declared: dict) -> None:
    """An action function that would take one argument twice."""
    inputs = declared["actions"][0]["inputs"]
    inputs.append(dict(inputs[0]))


def _two_secrets_named_alike(declared: dict) -> None:
    """Two secrets that would share one environment variable."""
    declared["secrets"] = [{"name": "token", "title": "Token"}] * 2


def _an_unknown_input_kind(declared: dict) -> None:
    """An input the run dialog could not draw."""
    declared["actions"][0]["inputs"][0]["kind"] = "date"


def _a_capitalised_action_name(declared: dict) -> None:
    """An action name that is not safe in a URL."""
    declared["actions"][0]["name"] = "Search"


def _a_hyphenated_input_name(declared: dict) -> None:
    """An input name Python could not take as an argument."""
    declared["actions"][0]["inputs"][0]["name"] = "search-for"


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (_no_actions, "actions: must not be empty"),
        (_two_actions_named_alike, "actions: two actions are named search"),
        (_two_inputs_named_alike, "actions[0].inputs: two inputs are named query"),
        (_two_secrets_named_alike, "secrets: two secrets are named token"),
        (
            _an_unknown_input_kind,
            "actions[0].inputs[0].kind: must be string, number or boolean",
        ),
        (_a_capitalised_action_name, f"actions[0].name: {SAFE_IN_URLS}"),
        (_a_hyphenated_input_name, f"actions[0].inputs[0].name: {VALID_VARIABLE}"),
    ],
)
def test_actions_and_their_inputs_are_well_formed(
    tmp_path: Path, change, error: str
) -> None:
    """The app can list each action, and draw and fill each input, unambiguously."""
    declared = _hn_search()
    change(declared)

    assert _errors_in(tmp_path, declared) == [error]


@pytest.mark.parametrize("seconds", [0, 21601])
def test_a_run_lasts_between_a_second_and_six_hours(
    tmp_path: Path, seconds: int
) -> None:
    """No action can ask to run forever, or for no time at all."""
    declared = _hn_search()
    declared["actions"][0]["timeout_seconds"] = seconds

    assert _errors_in(tmp_path, declared) == [
        "actions[0].timeout_seconds: must be 1 to 21600 seconds"
    ]


def test_every_error_is_reported_at_once(tmp_path: Path) -> None:
    """An author fixes a manifest in one pass, not one error per run."""
    declared = _hn_search()
    declared["id"] = "HN"
    declared["hosts"] = ["https://hn.algolia.com"]
    _two_actions_named_alike(declared)

    assert _errors_in(tmp_path, declared) == [
        f"id: {SAFE_IN_URLS}",
        "hosts[0]: must be a lowercase hostname alone: no scheme, port, path or"
        " wildcard",
        "actions: two actions are named search",
    ]


def test_a_missing_manifest_is_one_error(tmp_path: Path) -> None:
    """A folder with no manifest.json says so, rather than raising a traceback."""
    with pytest.raises(ManifestError) as refused:
        load_manifest(tmp_path / "manifest.json")

    assert refused.value.errors == ["manifest.json: does not exist"]


@pytest.mark.parametrize(
    ("content", "error"),
    [
        ('{"id": "hn-search",}', "manifest.json: is not valid JSON, line 1 column 20"),
        ('["hn-search"]', "manifest.json: must be a JSON object"),
    ],
)
def test_a_manifest_that_is_not_a_json_object_is_one_error(
    tmp_path: Path, content: str, error: str
) -> None:
    """Broken JSON points at where it broke, rather than raising a traceback."""
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ManifestError) as refused:
        load_manifest(path)

    assert refused.value.errors == [error]
