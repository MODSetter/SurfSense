# Composio Google Drive — E2E

Phase 1 Playwright coverage for the Composio Drive connector.

## Journey in this folder

| File | User expectation |
| --- | --- |
| `journey.spec.ts` | "I connect Google Drive, choose a file, wait for indexing, and SurfSense contains that file's content." |

## What "passes" actually proves

- The dashboard and connector dialog render for the authenticated user.
- The Composio Drive connector fixture can complete the happy OAuth setup.
- The selected Drive file config can be persisted.
- Pipeline service summarizes/embeds/chunks an indexed file end-to-end.
- Celery worker is reachable from the FastAPI process (queue + broker).
- `Document.content` contains the Drive canary token after indexing.

## Edge cases tested elsewhere

Playwright does not own backend edge cases. They are cheaper and easier
to localize in pytest:

- OAuth state freshness/tamper/malformed validation:
  `surfsense_backend/tests/unit/utils/test_oauth_security.py`
- OAuth denied callback and duplicate/reconnection branch:
  `surfsense_backend/tests/integration/composio/test_oauth_callback.py`
- Folder listing, selected file config persistence, and auth-expired
  classification:
  `surfsense_backend/tests/integration/composio/test_drive_folders_route.py`

## What "passes" does NOT prove

- Real Composio.dev integration (mocked).
- Real LLM summarization quality (`FakeListChatModel`).
- Real embedding semantics (constant 0.1 vectors).

These are intentional. Phase 1's deal is "the user-visible Drive
journey crosses the connector/indexing seams". Phase 2 can add opt-in
"live LLM" smoke tests under a separate workflow and a separate budget.

## Adding a fourth Composio toolkit (e.g. Slack)

1. Add fixture data to
   `surfsense_backend/tests/e2e/fakes/fixtures/<toolkit>_*.json`.
2. Extend `_Tools.execute()` in
   `surfsense_backend/tests/e2e/fakes/composio_module.py` to handle the
   new toolkit's tool slugs (`SLACK_FETCH_CONVERSATIONS`, etc.).
3. Add the toolkit to `_AuthConfigs.list()`.
4. Drop a sibling folder `tests/connectors/composio/<toolkit>/` with
   one `journey.spec.ts` that matches the user's expectation for that
   toolkit.

The fixtures in `tests/fixtures/connectors/composio-drive.fixture.ts`
are the template — copy + change `toolkit_id`.
