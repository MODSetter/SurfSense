import { expect, notionWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndex } from "../../helpers/api/connectors";
import { getEditorContent, listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_NOTION_PAGES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";
import { waitForDocumentByTitle, waitForIndexingComplete } from "../../helpers/waits/indexing";

/**
 * Proves Notion OAuth -> indexed Notion API pages -> stored source_markdown -> chat.
 *
 * The external Notion provider is faked at the OAuth token/API boundary;
 * SurfSense's own add/callback routes, encrypted config storage, connector
 * indexing endpoint, indexing pipeline, and chat retrieval remain real.
 */
test.describe("Notion connector journey", () => {
	test("user connects Notion through OAuth, indexes a page, and chats with the canary token", async ({
		page,
		request,
		apiToken,
		searchSpace,
		notionConnector,
		chatThread,
	}) => {
		test.setTimeout(180_000); // worker cold-start + summarize + embed + chunk

		expect(notionConnector.connector_type).toBe("NOTION_CONNECTOR");
		expect(notionConnector.is_indexable).toBe(true);
		expect(notionConnector.config._token_encrypted).toBe(true);
		expect(notionConnector.config.NOTION_INTEGRATION_TOKEN).toBeUndefined();
		expect(notionConnector.config.access_token).toBeTruthy();
		expect(notionConnector.config.workspace_id).toBe(FAKE_NOTION_PAGES.canary.workspaceId);
		expect(notionConnector.config.workspace_name).toBe(FAKE_NOTION_PAGES.canary.workspaceName);
		expect(notionConnector.config.bot_id).toBe(FAKE_NOTION_PAGES.canary.botId);

		await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();
		await expect(connectorDialog.getByRole("button", { name: "Manage" })).toBeVisible();

		await triggerIndex(request, apiToken, notionConnector.id, searchSpace.id, {});

		await waitForIndexingComplete(request, apiToken, notionConnector.id, searchSpace.id, {
			timeoutMs: 150_000,
			intervalMs: 1_500,
			minDocuments: 1,
		});

		await waitForDocumentByTitle(
			request,
			apiToken,
			searchSpace.id,
			FAKE_NOTION_PAGES.canary.title,
			{
				timeoutMs: 30_000,
			}
		);

		const docs = await listDocuments(request, apiToken, searchSpace.id);
		const canaryDoc = docs.find((d) => d.title === FAKE_NOTION_PAGES.canary.title);

		expect(canaryDoc, "Notion canary document must exist after indexing").toBeDefined();
		if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");
		expect(canaryDoc.document_type).toBe("NOTION_CONNECTOR");

		const editor = await getEditorContent(request, apiToken, searchSpace.id, canaryDoc.id);
		expect(
			editor.source_markdown,
			`canary token ${CANARY_TOKENS.notionCanary} should appear in editor source_markdown; ` +
				`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.notionCanary);
		expect(editor.document_type).toBe("NOTION_CONNECTOR");
		expect(editor.chunk_count).toBeGreaterThan(0);

		const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === notionConnector.id);
		expect(refreshed?.connector_type).toBe("NOTION_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(true);
		expect(refreshed?.last_indexed_at).not.toBeNull();

		const chat = await streamChatToCompletion(request, apiToken, {
			searchSpaceId: searchSpace.id,
			threadId: chatThread.id,
			query: `What is in my Notion page titled "${FAKE_NOTION_PAGES.canary.title}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Notion canary token after indexing; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.notionCanary);
	});
});
