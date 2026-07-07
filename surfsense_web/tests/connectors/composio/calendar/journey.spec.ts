import { expect, composioCalendarWithChatTest as test } from "../../../fixtures";
import { streamChatToCompletion } from "../../../helpers/api/chat";
import { listConnectors } from "../../../helpers/api/connectors";
import { listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_CALENDAR_EVENTS } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";

/**
 * Proves the Calendar wiring from OAuth fixture -> live Calendar tools -> chat.
 *
 * Composio Calendar is a live connector: it should not index documents into
 * the knowledge base. Chat should call Calendar tools against the connected
 * Composio account when the user asks about events.
 */
test.describe("Composio Calendar journey", () => {
	test("user connects Calendar and chats through live Calendar tools with the canary token", async ({
		page,
		request,
		apiToken,
		workspace,
		composioCalendarConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage External MCP Connectors" });
		await expect(connectorDialog).toBeVisible();

		const beforeChatDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeChatDocs).toHaveLength(0);

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query:
				`What Calendar event mentions ${CANARY_TOKENS.calendarCanary} next week? ` +
				`The event title is "${FAKE_CALENDAR_EVENTS.canary.summary}".`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Calendar canary token from live tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.calendarCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("search_calendar_events");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === composioCalendarConnector.id);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterChatDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterChatDocs).toHaveLength(0);
	});
});
