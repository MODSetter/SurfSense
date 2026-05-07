import { expect, confluenceWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndex } from "../../helpers/api/connectors";
import { getEditorContent, listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_CONFLUENCE_PAGES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";
import { waitForDocumentByTitle, waitForIndexingComplete } from "../../helpers/waits/indexing";

/**
 * Proves Confluence OAuth -> indexed Confluence pages -> stored source_markdown -> chat.
 *
 * The external Atlassian provider is faked at the OAuth token/resource and
 * Confluence page-fetch boundaries; SurfSense's own add/callback routes,
 * encrypted config storage, indexing endpoint, indexing pipeline, and chat
 * retrieval remain real.
 */
test.describe("Confluence connector journey", () => {
	test("user connects Confluence through OAuth, indexes a page, and chats with the canary token", async ({
		page,
		request,
		apiToken,
		searchSpace,
		confluenceConnector,
		chatThread,
	}) => {
		test.setTimeout(180_000); // worker cold-start + summarize + embed + chunk

		expect(confluenceConnector.connector_type).toBe("CONFLUENCE_CONNECTOR");
		expect(confluenceConnector.is_indexable).toBe(true);
		expect(confluenceConnector.config._token_encrypted).toBe(true);
		expect(confluenceConnector.config.cloud_id).toBe(FAKE_CONFLUENCE_PAGES.canary.cloudId);
		expect(confluenceConnector.config.base_url).toBe(FAKE_CONFLUENCE_PAGES.canary.baseUrl);
		expect(confluenceConnector.config.access_token).toBeTruthy();
		expect(confluenceConnector.config.CONFLUENCE_BASE_URL).toBeUndefined();
		expect(confluenceConnector.config.CONFLUENCE_EMAIL).toBeUndefined();
		expect(confluenceConnector.config.CONFLUENCE_API_TOKEN).toBeUndefined();

		await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();
		await connectorDialog.getByPlaceholder("Search").fill("Confluence");
		await expect(connectorDialog.getByText("Confluence", { exact: true })).toBeVisible();

		await triggerIndex(request, apiToken, confluenceConnector.id, searchSpace.id, {});

		await waitForIndexingComplete(request, apiToken, confluenceConnector.id, searchSpace.id, {
			timeoutMs: 150_000,
			intervalMs: 1_500,
			minDocuments: 1,
		});

		await waitForDocumentByTitle(
			request,
			apiToken,
			searchSpace.id,
			FAKE_CONFLUENCE_PAGES.canary.title,
			{
				timeoutMs: 30_000,
			}
		);

		const docs = await listDocuments(request, apiToken, searchSpace.id);
		const canaryDoc = docs.find((d) => d.title === FAKE_CONFLUENCE_PAGES.canary.title);

		expect(canaryDoc, "Confluence canary document must exist after indexing").toBeDefined();
		if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");
		expect(canaryDoc.document_type).toBe("CONFLUENCE_CONNECTOR");

		const editor = await getEditorContent(request, apiToken, searchSpace.id, canaryDoc.id);
		expect(
			editor.source_markdown,
			`canary token ${CANARY_TOKENS.confluenceCanary} should appear in editor source_markdown; ` +
				`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.confluenceCanary);
		expect(editor.document_type).toBe("CONFLUENCE_CONNECTOR");
		expect(editor.chunk_count).toBeGreaterThan(0);

		const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === confluenceConnector.id);
		expect(refreshed?.connector_type).toBe("CONFLUENCE_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(true);
		expect(refreshed?.last_indexed_at).not.toBeNull();

		const chat = await streamChatToCompletion(request, apiToken, {
			searchSpaceId: searchSpace.id,
			threadId: chatThread.id,
			query: `What is in my Confluence page titled "${FAKE_CONFLUENCE_PAGES.canary.title}"?`,
		});
		expect(
			chat.assistantText,
			`chat agent should surface Confluence canary token after indexing; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.confluenceCanary);
	});
});
