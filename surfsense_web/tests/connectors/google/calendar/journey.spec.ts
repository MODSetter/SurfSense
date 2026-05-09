import { expect, nativeCalendarWithChatTest as test } from "../../../fixtures";
import { streamChatToCompletion } from "../../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../../helpers/api/connectors";
import { listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_CALENDAR_EVENTS } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";

/**
 * Proves the native Calendar wiring from Google OAuth fixture -> live Calendar
 * tools -> chat.
 *
 * Native Calendar is live-tool only: the public indexing route returns
 * indexing_started=false and chat should call Calendar tools.
 */
test.describe("Native Google Calendar journey", () => {
	test("user connects native Calendar and chats through live Calendar tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		searchSpace,
		nativeCalendarConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(nativeCalendarConnector.connector_type).toBe("GOOGLE_CALENDAR_CONNECTOR");
		expect(nativeCalendarConnector.is_indexable).toBe(false);
		expect(nativeCalendarConnector.config._token_encrypted).toBe(true);
		expect(nativeCalendarConnector.config.composio_connected_account_id).toBeUndefined();

		await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, searchSpace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			nativeCalendarConnector.id,
			searchSpace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			searchSpaceId: searchSpace.id,
			threadId: chatThread.id,
			query:
				`What Calendar event mentions ${CANARY_TOKENS.calendarCanary} next week? ` +
				`The event title is "${FAKE_CALENDAR_EVENTS.canary.summary}".`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface native Calendar canary token from live tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.calendarCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("search_calendar_events");

		const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === nativeCalendarConnector.id);
		expect(refreshed?.connector_type).toBe("GOOGLE_CALENDAR_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, searchSpace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
