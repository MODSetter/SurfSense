import { expect, composioGmailWithChatTest as test } from "../../../fixtures";
import { streamChatToCompletion } from "../../../helpers/api/chat";
import { listConnectors } from "../../../helpers/api/connectors";
import { listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_GMAIL_MESSAGES } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";

/**
 * Proves the Gmail wiring from OAuth fixture -> live Gmail tools -> chat.
 *
 * Gmail is a live connector: it should not index documents into the
 * knowledge base. Chat should call Gmail tools against the connected
 * Composio account when the user asks about email.
 */
test.describe("Composio Gmail journey", () => {
	test("user connects Gmail and chats through live Gmail tools with the canary token", async ({
		page,
		request,
		apiToken,
		workspace,
		composioGmailConnector,
		chatThread,
	}) => {
		test.setTimeout(90_000); // worker cold-start + live tool chat

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "MCP Connectors" });
		await expect(connectorDialog).toBeVisible();

		const beforeChatDocs = await listDocuments(request, apiToken, workspace.id);
		expect(beforeChatDocs).toHaveLength(0);

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: `What is in my Gmail message titled "${FAKE_GMAIL_MESSAGES.canary.subject}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Gmail canary token from live tools; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.gmailCanary);

		const eventText = JSON.stringify(chat.events);
		expect(eventText).toContain("search_gmail");
		expect(eventText).toContain("read_gmail_email");

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === composioGmailConnector.id);
		expect(refreshed?.last_indexed_at).toBeNull();

		const afterChatDocs = await listDocuments(request, apiToken, workspace.id);
		expect(afterChatDocs).toHaveLength(0);
	});
});
