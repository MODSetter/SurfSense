import { expect, composioGmailWithChatTest as test } from "../../../fixtures";
import { streamChatToCompletion } from "../../../helpers/api/chat";
import {
	listConnectors,
	triggerIndexByDateRange,
} from "../../../helpers/api/connectors";
import { getEditorContent, listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_GMAIL_MESSAGES } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";
import { waitForDocumentByTitle, waitForIndexingComplete } from "../../../helpers/waits/indexing";

/**
 * Proves the Gmail wiring from OAuth fixture -> date-range indexing ->
 * Gmail message markdown -> stored source_markdown -> chat.
 *
 * Unlike Drive, Gmail has no file/folder selection config. The E2E
 * hits the same date-range index contract the production route uses.
 */
test.describe("Composio Gmail journey", () => {
	test("user connects Gmail, indexes messages, and chats with the canary token", async ({
		page,
		request,
		apiToken,
		searchSpace,
		composioGmailConnector,
		chatThread,
	}) => {
		test.setTimeout(180_000); // worker cold-start + summarize + embed + chunk

		await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();
		await expect(connectorDialog.getByRole("button", { name: "Manage" })).toBeVisible();

		await triggerIndexByDateRange(request, apiToken, composioGmailConnector.id, searchSpace.id, {
			startDate: "2025-01-01",
			endDate: "2026-12-31",
		});

		await waitForIndexingComplete(request, apiToken, composioGmailConnector.id, searchSpace.id, {
			timeoutMs: 150_000,
			intervalMs: 1_500,
			minDocuments: 1,
		});

		await waitForDocumentByTitle(
			request,
			apiToken,
			searchSpace.id,
			FAKE_GMAIL_MESSAGES.canary.subject,
			{ timeoutMs: 30_000 }
		);

		const docs = await listDocuments(request, apiToken, searchSpace.id);
		const canaryDoc = docs.find((d) => d.title === FAKE_GMAIL_MESSAGES.canary.subject);

		expect(canaryDoc, "canary Gmail document must exist after indexing").toBeDefined();
		if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");

		const editor = await getEditorContent(request, apiToken, searchSpace.id, canaryDoc.id);
		expect(
			editor.source_markdown,
			`canary token ${CANARY_TOKENS.gmailCanary} should appear in editor source_markdown; ` +
				`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.gmailCanary);
		expect(editor.source_markdown).toContain(`**From:** ${FAKE_GMAIL_MESSAGES.canary.from}`);
		expect(editor.source_markdown).toContain("## Message Content");
		expect(editor.chunk_count).toBeGreaterThan(0);

		const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === composioGmailConnector.id);
		expect(refreshed?.last_indexed_at).not.toBeNull();

		const chat = await streamChatToCompletion(request, apiToken, {
			searchSpaceId: searchSpace.id,
			threadId: chatThread.id,
			query: `What is in my Gmail message titled "${FAKE_GMAIL_MESSAGES.canary.subject}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Gmail canary token after indexing; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.gmailCanary);
	});
});
