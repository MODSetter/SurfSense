/**
 * Central export of all Playwright fixtures used across the E2E suite.
 *
 * Specs import `test` and `expect` from here instead of `@playwright/test`
 * directly so that adding a new fixture (e.g. for a new connector) is a
 * one-line change for every spec that needs it.
 *
 * Inheritance chain:
 *   base (@playwright/test)
 *     └─ searchSpaceFixtures   — apiToken, searchSpace
 *         ├─ composioDriveFixtures — composioDriveConnector
 *         │   └─ composioDriveWithChatTest — chatThread
 *         └─ composioGmailFixtures — composioGmailConnector
 *             └─ composioGmailWithChatTest — chatThread
 *         └─ composioCalendarFixtures — composioCalendarConnector
 *             └─ composioCalendarWithChatTest — chatThread
 *
 * To add a new connector (Gmail, Slack, manual upload, etc.):
 *   1. Add a fixture file under `fixtures/connectors/<name>.fixture.ts`.
 *   2. Re-export it here under a new typed `test` if the new fixture
 *      doesn't compose cleanly into the existing chain.
 */
export { expect } from "@playwright/test";
export { chatThreadFixtures } from "./chat-thread.fixture";
export { composioCalendarFixtures } from "./connectors/composio-calendar.fixture";
export { composioDriveFixtures } from "./connectors/composio-drive.fixture";
export { composioGmailFixtures } from "./connectors/composio-gmail.fixture";
export { searchSpaceFixtures } from "./search-space.fixture";

import { type ChatThreadFixtures, chatThreadFixtures } from "./chat-thread.fixture";
import { composioCalendarFixtures } from "./connectors/composio-calendar.fixture";
import { composioDriveFixtures } from "./connectors/composio-drive.fixture";
import { composioGmailFixtures } from "./connectors/composio-gmail.fixture";
import { searchSpaceFixtures } from "./search-space.fixture";

/** Default `test` for specs that just need auth + a clean search space. */
export const test = searchSpaceFixtures;
/** `test` for specs that also need a pre-connected Composio Drive connector. */
export const composioDriveTest = composioDriveFixtures;
/** `test` for Drive specs that also need a chat thread. */
export const composioDriveWithChatTest =
	composioDriveFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected Composio Gmail connector. */
export const composioGmailTest = composioGmailFixtures;
/** `test` for Gmail specs that also need a chat thread. */
export const composioGmailWithChatTest =
	composioGmailFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected Composio Calendar connector. */
export const composioCalendarTest = composioCalendarFixtures;
/** `test` for Calendar specs that also need a chat thread. */
export const composioCalendarWithChatTest =
	composioCalendarFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
