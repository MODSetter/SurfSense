import { expect, nativeGmailWithChatTest as test } from "../../../fixtures";
import { streamChatToCompletion } from "../../../helpers/api/chat";
import { listConnectors, triggerIndexExpectDisabled } from "../../../helpers/api/connectors";
import { listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_GMAIL_MESSAGES } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";

/**
 * Proves the native Gmail wiring from Google OAuth fixture -> live Gmail
 * tools -> chat.
 *
 * Native Gmail is currently live-tool only: the public indexing route
 * returns indexing_started=false and chat should call Gmail tools.
 */
test.describe("Native Google Gmail journey", () => {
	test("user connects native Gmail and chats through live Gmail tools with indexing disabled", async ({
		page,
		request,
		apiToken,
		workspace,
		nativeGmailConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		expect(nativeGmailConnector.connector_type).toBe("GOOGLE_GMAIL_CONNECTOR");
		expect(nativeGmailConnector.is_indexable).toBe(false);
		expect(nativeGmailConnector.config._token_encrypted).toBe(true);
		expect(nativeGmailConnector.config.composio_connected_account_id).toBeUndefined();

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();

		const beforeDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeDocs).toHaveLength(0);

		const disabledIndex = await triggerIndexExpectDisabled(
			request,
			apiToken,
			nativeGmailConnector.id,
			workspace.id
		);
		expect(disabledIndex.message ?? "").toContain("real-time agent tools");
		expect(disabledIndex.message ?? "").toContain("background indexing is disabled");

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my Gmail message titled "${FAKE_GMAIL_MESSAGES.canary.subject}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface native Gmail canary token from live tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.gmailCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("search_gmail");
		expect(eventText).toContain("read_gmail_email");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === nativeGmailConnector.id);
		expect(refreshed?.connector_type).toBe("GOOGLE_GMAIL_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(false);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterDocs).toHaveLength(0);
	});
});
