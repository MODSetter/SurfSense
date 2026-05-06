"""Strict drop-in replacement for the `composio` Python SDK.

Registered as `sys.modules["composio"]` by `tests/e2e/run_backend.py`
and `tests/e2e/run_celery.py` BEFORE any production code imports
`composio`. From that point on, every `from composio import Composio`
in production resolves to `Composio` defined here.

Every class implements __getattr__ that raises NotImplementedError on
unknown attributes. A future production code path that introduces a
new SDK call (e.g. `client.bulk_operations.run`) fails CI loudly with
a clear "add this surface to the fake" message instead of silently
passing through to the real SDK.

Scenario branching is read from the request-scoped ContextVar in
`tests/e2e/middleware/scenario.py`, set by the X-E2E-Scenario header.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "drive_files.json"
_DRIVE_DOWNLOAD_DIR = Path("/tmp/surfsense-e2e-composio-downloads")


def _load_drive_fixture() -> dict[str, Any]:
    """Load the canned Drive fixture once per process."""
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_DRIVE_FIXTURE = _load_drive_fixture()


def _get_scenario() -> str:
    """Return the current X-E2E-Scenario, defaulting to 'happy'.

    Imported lazily so the fake module can be loaded BEFORE
    `tests.e2e.middleware.scenario` is importable (during sys.modules
    hijack at the very top of the entrypoint).
    """
    try:
        from tests.e2e.middleware.scenario import current_scenario

        return current_scenario()
    except Exception:
        return "happy"


# ---------------------------------------------------------------------------
# Strict mixin: every fake class raises on unknown attribute access
# ---------------------------------------------------------------------------


class _StrictFakeMixin:
    """Base class for fakes. Any unknown attribute access fails loudly."""

    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E Composio fake missing surface: {self._component_name}.{name!r}. "
            f"If production code needs this, add an explicit method to "
            f"surfsense_backend/tests/e2e/fakes/composio_module.py — "
            f"the strict fake refuses to silently fall through to the real SDK."
        )


# ---------------------------------------------------------------------------
# Result objects mimicking the real SDK's response dataclasses
# ---------------------------------------------------------------------------


class _ConnectionRequest:
    """Mimics composio.connected_accounts.initiate(...) return value."""

    def __init__(self, *, redirect_url: str, account_id: str) -> None:
        self.redirect_url = redirect_url
        self.id = account_id


class _ConnectedAccount:
    """Mimics a connected_account row returned by wait_for_connection / refresh."""

    def __init__(
        self,
        *,
        account_id: str,
        status: str = "ACTIVE",
        redirect_url: str | None = None,
        access_token: str = "fake-e2e-access-token-not-real-do-not-use-32chars",
    ) -> None:
        self.id = account_id
        self.status = status
        self.redirect_url = redirect_url
        self.state = _AccountState(access_token=access_token)


class _AccountState:
    def __init__(self, *, access_token: str) -> None:
        self.val = _AccountStateVal(access_token=access_token)


class _AccountStateVal:
    def __init__(self, *, access_token: str) -> None:
        self.access_token = access_token


class _AuthConfig:
    """Mimics one auth_config row returned by client.auth_configs.list().items."""

    def __init__(self, *, config_id: str, toolkit_slug: str) -> None:
        self.id = config_id
        self.toolkit = _Toolkit(slug=toolkit_slug)


class _Toolkit:
    def __init__(self, *, slug: str) -> None:
        self.slug = slug


class _AuthConfigsListResult:
    def __init__(self, items: list[_AuthConfig]) -> None:
        self.items = items


# ---------------------------------------------------------------------------
# Sub-clients on the Composio top-level object
# ---------------------------------------------------------------------------


class _ConnectedAccounts(_StrictFakeMixin):
    """Strict fake for client.connected_accounts.*"""

    _component_name = "connected_accounts"

    def initiate(
        self,
        *,
        user_id: str,
        auth_config_id: str,
        callback_url: str,
        allow_multiple: bool = True,
        **_: Any,
    ) -> _ConnectionRequest:
        scenario = _get_scenario()
        # Synthesize a deterministic account ID. Same toolkit on the same
        # entity yields the same ID so the duplicate-connection scenario
        # exercises the reconnect branch in composio_routes.py.
        toolkit_id = auth_config_id.replace("auth-config-", "")
        account_id = f"fake-acct-{toolkit_id}-{user_id}"

        # The SDK's redirect_url normally points to Composio's hosted OAuth
        # UI which then bounces to the third-party provider. In E2E we
        # short-circuit straight back to OUR same-origin callback to avoid
        # any real network requirement.
        if scenario == "denied":
            redirect = (
                f"{callback_url}&error=access_denied"
                if "?" in callback_url
                else f"{callback_url}?error=access_denied"
            )
        else:
            redirect = (
                f"{callback_url}&connectedAccountId={account_id}"
                if "?" in callback_url
                else f"{callback_url}?connectedAccountId={account_id}"
            )
        logger.info(
            "[fake-composio] initiate scenario=%s toolkit=%s redirect=%s",
            scenario,
            toolkit_id,
            redirect,
        )
        return _ConnectionRequest(redirect_url=redirect, account_id=account_id)

    def wait_for_connection(
        self, *, id: str, timeout: float = 30.0, **_: Any
    ) -> _ConnectedAccount:
        return _ConnectedAccount(account_id=id, status="ACTIVE")

    def get(self, *, nanoid: str, **_: Any) -> _ConnectedAccount:
        return _ConnectedAccount(account_id=nanoid, status="ACTIVE")

    def delete(self, account_id: str, /, **_: Any) -> dict[str, Any]:
        logger.info("[fake-composio] delete account=%s", account_id)
        return {"success": True, "id": account_id}

    def refresh(
        self,
        *,
        nanoid: str,
        body_redirect_url: str | None = None,
        **_: Any,
    ) -> _ConnectedAccount:
        return _ConnectedAccount(
            account_id=nanoid,
            status="ACTIVE",
            redirect_url=body_redirect_url,
        )


class _AuthConfigs(_StrictFakeMixin):
    """Strict fake for client.auth_configs.*"""

    _component_name = "auth_configs"

    def list(self, **_: Any) -> _AuthConfigsListResult:
        # Return one auth config per toolkit we plan to test. The real
        # SDK lets you have multiple, but one is enough for E2E.
        return _AuthConfigsListResult(
            items=[
                _AuthConfig(config_id="auth-config-googledrive", toolkit_slug="googledrive"),
                _AuthConfig(config_id="auth-config-gmail", toolkit_slug="gmail"),
                _AuthConfig(
                    config_id="auth-config-googlecalendar",
                    toolkit_slug="googlecalendar",
                ),
            ]
        )


class _Tools(_StrictFakeMixin):
    """Strict fake for client.tools.*"""

    _component_name = "tools"

    def execute(
        self,
        *,
        slug: str,
        connected_account_id: str,
        user_id: str | None = None,
        arguments: dict[str, Any] | None = None,
        dangerously_skip_version_check: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        scenario = _get_scenario()
        args = arguments or {}
        logger.info(
            "[fake-composio] tools.execute slug=%s scenario=%s args=%s",
            slug,
            scenario,
            list(args.keys()),
        )

        if scenario == "auth_expired":
            # Match the error strings that composio_routes.py classifies
            # as authentication failures (see lines ~720-728).
            raise _AuthExpiredError(
                "Token has been expired or revoked. (HTTP 401: invalid_grant)"
            )

        if slug == "GOOGLEDRIVE_LIST_FILES":
            return _drive_list_files(args)
        if slug == "GOOGLEDRIVE_DOWNLOAD_FILE":
            return _drive_download_file(args)
        if slug == "GOOGLEDRIVE_GET_FILE_METADATA":
            return _drive_get_metadata(args)
        if slug == "GOOGLEDRIVE_GET_CHANGES_START_PAGE_TOKEN":
            return {"data": {"startPageToken": "fake-start-page-token-1"}}
        if slug == "GOOGLEDRIVE_LIST_CHANGES":
            return {"data": {"changes": [], "newStartPageToken": "fake-start-page-token-1"}}
        if slug == "GOOGLEDRIVE_GET_ABOUT":
            # Used by ComposioService.get_connected_account_email for
            # googledrive. Returning a fake email lets the connector get a
            # nice display name; failure is non-fatal.
            return {"data": {"user": {"emailAddress": "e2e-fake@surfsense.example"}}}
        if slug == "GMAIL_GET_PROFILE":
            return {"data": {"emailAddress": "e2e-fake@surfsense.example"}}
        if slug == "GOOGLECALENDAR_CALENDARS_LIST":
            return {
                "data": {
                    "items": [
                        {
                            "id": "primary",
                            "summary": "e2e-fake@surfsense.example",
                            "primary": True,
                        }
                    ]
                }
            }

        # No silent passthrough: a slug we have not modelled is a test bug.
        raise NotImplementedError(
            f"E2E Composio fake has no handler for tool slug {slug!r}. "
            f"Add it to surfsense_backend/tests/e2e/fakes/composio_module.py "
            f"in `_Tools.execute` if production code needs it."
        )


# ---------------------------------------------------------------------------
# Drive tool handlers
# ---------------------------------------------------------------------------


def _drive_list_files(args: dict[str, Any]) -> dict[str, Any]:
    """Mimic GOOGLEDRIVE_LIST_FILES.

    The real SDK accepts a Drive-style `q=` query like
    `'<folder_id>' in parents and trashed = false ...`. We parse out the
    folder id and serve the matching fixture list.
    """
    q = args.get("q", "")
    folder_id = "root"
    if "in parents" in q:
        # q looks like:  '<folder_id>' in parents and trashed = false ...
        try:
            folder_id = q.split("'")[1]
        except IndexError:
            folder_id = "root"

    files = _filter_drive_files_for_query(q, _DRIVE_FIXTURE.get(folder_id, []))
    return {
        "data": {
            "files": files,
            "nextPageToken": None,
        }
    }


def _extract_quoted_value(q: str, anchor: str) -> str | None:
    anchor_idx = q.find(anchor)
    if anchor_idx == -1:
        return None

    after_anchor = q[anchor_idx + len(anchor) :]
    first_quote_idx = after_anchor.find("'")
    if first_quote_idx == -1:
        return None

    after_first_quote = after_anchor[first_quote_idx + 1 :]
    second_quote_idx = after_first_quote.find("'")
    if second_quote_idx == -1:
        return None

    return after_first_quote[:second_quote_idx]


def _filter_drive_files_for_query(q: str, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = list(files)

    if "trashed = false" in q:
        filtered = [entry for entry in filtered if entry.get("trashed") is not True]

    excluded_mime_type = _extract_quoted_value(q, "mimeType !=")
    if excluded_mime_type:
        filtered = [
            entry for entry in filtered if entry.get("mimeType") != excluded_mime_type
        ]

    included_mime_type = _extract_quoted_value(q, "mimeType =")
    if included_mime_type:
        filtered = [
            entry for entry in filtered if entry.get("mimeType") == included_mime_type
        ]

    return filtered


def _drive_download_file(args: dict[str, Any]) -> dict[str, Any]:
    """Mimic GOOGLEDRIVE_DOWNLOAD_FILE.

    The real SDK writes the downloaded bytes to a local file and returns
    the path. composio_service.py then reads bytes from that path. We
    reproduce that behaviour by writing fixture content into a tmp
    directory and returning the path.
    """
    file_id = args.get("file_id", "")
    contents = _DRIVE_FIXTURE.get("_file_contents", {}).get(file_id)
    if contents is None:
        # Unknown file id is a test bug, fail loudly.
        raise NotImplementedError(
            f"E2E Composio fake has no canned content for file_id={file_id!r}. "
            f"Add it under '_file_contents' in "
            f"surfsense_backend/tests/e2e/fakes/fixtures/drive_files.json."
        )

    _DRIVE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _DRIVE_DOWNLOAD_DIR / f"{file_id}.txt"
    out_path.write_text(contents, encoding="utf-8")
    return {
        "data": {
            "file_path": str(out_path),
            "file_name": f"{file_id}.txt",
            "size": len(contents),
        }
    }


def _drive_get_metadata(args: dict[str, Any]) -> dict[str, Any]:
    """Mimic GOOGLEDRIVE_GET_FILE_METADATA."""
    file_id = args.get("file_id", "")
    # Search every folder fixture for the file
    for items in _DRIVE_FIXTURE.values():
        if not isinstance(items, list):
            continue
        for entry in items:
            if entry.get("id") == file_id:
                return {"data": entry}
    raise NotImplementedError(
        f"E2E fake: no metadata fixture for file_id={file_id!r}. "
        f"Add it to drive_files.json."
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class _AuthExpiredError(Exception):
    """Raised by the fake when scenario=auth_expired.

    composio_service.execute_tool catches every exception and surfaces
    str(error) inside the result dict; composio_routes.py then classifies
    "expired or revoked" / "401" tokens and sets connector.config.auth_expired.
    """


# ---------------------------------------------------------------------------
# Top-level Composio class — the only public symbol production imports
# ---------------------------------------------------------------------------


class Composio(_StrictFakeMixin):
    """Drop-in replacement for `composio.Composio`.

    Production calls:  `Composio(api_key=..., file_download_dir=...)`
    """

    _component_name = "Composio"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        file_download_dir: str | None = None,
        **_: Any,
    ) -> None:
        self.api_key = api_key
        self.file_download_dir = file_download_dir
        self.connected_accounts = _ConnectedAccounts()
        self.tools = _Tools()
        self.auth_configs = _AuthConfigs()
        logger.info(
            "[fake-composio] Composio() constructed (E2E mode, no real network)"
        )


# Public re-exports so `from composio import Composio` resolves correctly
# when this module is registered as sys.modules["composio"].
__all__ = ["Composio"]
