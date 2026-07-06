import { expect, nativeDropboxWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import { listConnectors, triggerIndex, updateConnectorConfig } from "../../helpers/api/connectors";
import { getEditorContent, listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_DROPBOX_FILES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";
import { waitForDocumentByTitle, waitForIndexingComplete } from "../../helpers/waits/indexing";

/**
 * Proves the native Dropbox wiring from Dropbox OAuth fixture -> selection
 * persistence -> Dropbox API indexing -> stored source_markdown -> chat.
 *
 * The folder picker is intentionally bypassed; this journey exercises the
 * persisted config and indexing contract the picker ultimately feeds.
 */
test.describe("Native Dropbox journey", () => {
	test("user connects Dropbox, selects a file, indexes it, and chats with the canary token", async ({
		page,
		request,
		apiToken,
		workspace,
		nativeDropboxConnector,
		chatThread,
	}) => {
		test.setTimeout(240_000); // worker cold-start + Docling + summarize + embed + chunk

		expect(nativeDropboxConnector.connector_type).toBe("DROPBOX_CONNECTOR");
		expect(nativeDropboxConnector.is_indexable).toBe(true);
		expect(nativeDropboxConnector.config._token_encrypted).toBe(true);
		expect(nativeDropboxConnector.config.composio_connected_account_id).toBeUndefined();

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();

		const selectedFiles = [
			{
				id: FAKE_DROPBOX_FILES.canary.id,
				name: FAKE_DROPBOX_FILES.canary.name,
				mimeType: FAKE_DROPBOX_FILES.canary.mimeType,
			},
			{
				id: FAKE_DROPBOX_FILES.pdf.id,
				name: FAKE_DROPBOX_FILES.pdf.name,
				mimeType: FAKE_DROPBOX_FILES.pdf.mimeType,
			},
		];
		// Keep the shared Drive-style body shape. Dropbox currently defaults
		// these internally because the indexer expects max_files/use_delta_sync.
		const indexingOptions = {
			max_files_per_folder: 10,
			incremental_sync: false,
			include_subfolders: false,
		};

		await updateConnectorConfig(request, apiToken, nativeDropboxConnector.id, {
			...nativeDropboxConnector.config,
			selected_folders: [],
			selected_files: selectedFiles,
			indexing_options: indexingOptions,
		});

		await triggerIndex(request, apiToken, nativeDropboxConnector.id, workspace.id, {
			files: selectedFiles,
			indexing_options: indexingOptions,
		});

		await waitForIndexingComplete(request, apiToken, nativeDropboxConnector.id, workspace.id, {
			timeoutMs: 240_000,
			intervalMs: 1_500,
			minDocuments: 2,
		});

		await waitForDocumentByTitle(request, apiToken, workspace.id, FAKE_DROPBOX_FILES.canary.name, {
			timeoutMs: 30_000,
		});
		await waitForDocumentByTitle(request, apiToken, workspace.id, FAKE_DROPBOX_FILES.pdf.name, {
			timeoutMs: 60_000,
		});

		const docs = await listDocuments(request, apiToken, workspace.id);
		const canaryDoc = docs.find((d) => d.title === FAKE_DROPBOX_FILES.canary.name);
		const pdfDoc = docs.find((d) => d.title === FAKE_DROPBOX_FILES.pdf.name);

		expect(canaryDoc, "Dropbox canary document must exist after indexing").toBeDefined();
		if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");
		expect(canaryDoc.document_type).toBe("DROPBOX_FILE");
		expect(pdfDoc, "Dropbox PDF document must exist after indexing").toBeDefined();
		if (!pdfDoc) throw new Error("unreachable: pdfDoc asserted defined above");
		expect(pdfDoc.document_type).toBe("DROPBOX_FILE");

		const editor = await getEditorContent(request, apiToken, workspace.id, canaryDoc.id);
		expect(
			editor.source_markdown,
			`canary token ${CANARY_TOKENS.dropboxCanary} should appear in editor source_markdown; ` +
				`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.dropboxCanary);
		expect(editor.document_type).toBe("DROPBOX_FILE");
		expect(editor.chunk_count).toBeGreaterThan(0);

		const pdfEditor = await getEditorContent(request, apiToken, workspace.id, pdfDoc.id);
		expect(
			pdfEditor.source_markdown,
			`PDF canary token ${CANARY_TOKENS.dropboxPdfCanary} should appear in editor source_markdown; ` +
				`got first 200 chars: ${pdfEditor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.dropboxPdfCanary);
		expect(pdfEditor.document_type).toBe("DROPBOX_FILE");
		expect(pdfEditor.chunk_count).toBeGreaterThan(0);

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === nativeDropboxConnector.id);
		expect(refreshed?.connector_type).toBe("DROPBOX_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(true);
		expect(refreshed?.last_indexed_at).not.toBeNull();

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: "What is in my e2e-dropbox-canary.txt Dropbox file?",
		});
		expect(
			chat.assistantText,
			"chat agent should surface Dropbox canary token after indexing; " +
				`got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.dropboxCanary);

		const pdfChat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: "What is in my e2e-dropbox-canary.pdf Dropbox file?",
		});
		expect(
			pdfChat.assistantText,
			"chat agent should surface Dropbox PDF canary token after indexing; " +
				`got: ${pdfChat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.dropboxPdfCanary);
	});
});
