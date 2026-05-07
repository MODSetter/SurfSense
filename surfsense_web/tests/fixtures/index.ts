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
 *         └─ nativeDriveFixtures — nativeDriveConnector
 *             └─ nativeDriveWithChatTest — chatThread
 *         └─ nativeGmailFixtures — nativeGmailConnector
 *             └─ nativeGmailWithChatTest — chatThread
 *         └─ nativeCalendarFixtures — nativeCalendarConnector
 *             └─ nativeCalendarWithChatTest — chatThread
 *         └─ notionFixtures — notionConnector
 *             └─ notionWithChatTest — chatThread
 *         └─ confluenceFixtures — confluenceConnector
 *             └─ confluenceWithChatTest — chatThread
 *         └─ linearFixtures — linearConnector
 *             └─ linearWithChatTest — chatThread
 *         └─ jiraFixtures — jiraConnector
 *             └─ jiraWithChatTest — chatThread
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
export { confluenceFixtures } from "./connectors/confluence.fixture";
export { jiraFixtures } from "./connectors/jira.fixture";
export { linearFixtures } from "./connectors/linear.fixture";
export { nativeCalendarFixtures } from "./connectors/native-calendar.fixture";
export { nativeDriveFixtures } from "./connectors/native-drive.fixture";
export { nativeGmailFixtures } from "./connectors/native-gmail.fixture";
export { notionFixtures } from "./connectors/notion.fixture";
export { searchSpaceFixtures } from "./search-space.fixture";

import { type ChatThreadFixtures, chatThreadFixtures } from "./chat-thread.fixture";
import { composioCalendarFixtures } from "./connectors/composio-calendar.fixture";
import { composioDriveFixtures } from "./connectors/composio-drive.fixture";
import { composioGmailFixtures } from "./connectors/composio-gmail.fixture";
import { confluenceFixtures } from "./connectors/confluence.fixture";
import { jiraFixtures } from "./connectors/jira.fixture";
import { linearFixtures } from "./connectors/linear.fixture";
import { nativeCalendarFixtures } from "./connectors/native-calendar.fixture";
import { nativeDriveFixtures } from "./connectors/native-drive.fixture";
import { nativeGmailFixtures } from "./connectors/native-gmail.fixture";
import { notionFixtures } from "./connectors/notion.fixture";
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
/** `test` for specs that also need a pre-connected native Google Drive connector. */
export const nativeDriveTest = nativeDriveFixtures;
/** `test` for native Drive specs that also need a chat thread. */
export const nativeDriveWithChatTest =
	nativeDriveFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected native Gmail connector. */
export const nativeGmailTest = nativeGmailFixtures;
/** `test` for native Gmail specs that also need a chat thread. */
export const nativeGmailWithChatTest =
	nativeGmailFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected native Calendar connector. */
export const nativeCalendarTest = nativeCalendarFixtures;
/** `test` for native Calendar specs that also need a chat thread. */
export const nativeCalendarWithChatTest =
	nativeCalendarFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected Notion connector. */
export const notionTest = notionFixtures;
/** `test` for Notion specs that also need a chat thread. */
export const notionWithChatTest = notionFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected Confluence connector. */
export const confluenceTest = confluenceFixtures;
/** `test` for Confluence specs that also need a chat thread. */
export const confluenceWithChatTest =
	confluenceFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected Linear connector. */
export const linearTest = linearFixtures;
/** `test` for Linear specs that also need a chat thread. */
export const linearWithChatTest = linearFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
/** `test` for specs that also need a pre-connected Jira connector. */
export const jiraTest = jiraFixtures;
/** `test` for Jira specs that also need a chat thread. */
export const jiraWithChatTest = jiraFixtures.extend<ChatThreadFixtures>(chatThreadFixtures);
