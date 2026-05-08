import { expect, nativeDriveWithChatTest as test } from "../../../fixtures";
import { streamChatToCompletion } from "../../../helpers/api/chat";
import {
	listConnectors,
	triggerIndex,
	updateConnectorConfig,
} from "../../../helpers/api/connectors";
import { getEditorContent, listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_DRIVE_FILES } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";
import { waitForDocumentByTitle, waitForIndexingComplete } from "../../../helpers/waits/indexing";

/**
 * Proves the native Drive wiring from Google OAuth fixture -> selection
 * persistence -> native Drive API indexing -> stored source_markdown -> chat.
 *
 * Google Picker is intentionally bypassed; this journey exercises the
 * persisted config and indexing contract the Picker ultimately feeds.
 */
test.describe("Native Google Drive journey", () => {
	test("user connects native Drive, selects a file, indexes it, and chats with the canary token", async ({
		page,
		request,
		apiToken,
		searchSpace,
		nativeDriveConnector,
		chatThread,
	}) => {
		test.setTimeout(240_000); // worker cold-start + Docling + summarize + embed + chunk

		expect(nativeDriveConnector.connector_type).toBe("GOOGLE_DRIVE_CONNECTOR");
		expect(nativeDriveConnector.is_indexable).toBe(true);
		expect(nativeDriveConnector.config._token_encrypted).toBe(true);
		expect(nativeDriveConnector.config.composio_connected_account_id).toBeUndefined();

		await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		await openConnectorPopup(page);
		const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
		await expect(connectorDialog).toBeVisible();

		const selectedFiles = [
			{
				id: FAKE_DRIVE_FILES.canary.id,
				name: FAKE_DRIVE_FILES.canary.name,
				mimeType: FAKE_DRIVE_FILES.canary.mimeType,
			},
			{
				id: FAKE_DRIVE_FILES.pdfNative.id,
				name: FAKE_DRIVE_FILES.pdfNative.name,
				mimeType: FAKE_DRIVE_FILES.pdfNative.mimeType,
			},
		];
		const indexingOptions = {
			max_files_per_folder: 10,
			incremental_sync: false,
			include_subfolders: false,
		};

		await updateConnectorConfig(request, apiToken, nativeDriveConnector.id, {
			...nativeDriveConnector.config,
			selected_folders: [],
			selected_files: selectedFiles,
			indexing_options: indexingOptions,
		});

		await triggerIndex(request, apiToken, nativeDriveConnector.id, searchSpace.id, {
			files: selectedFiles,
			indexing_options: indexingOptions,
		});

		await waitForIndexingComplete(request, apiToken, nativeDriveConnector.id, searchSpace.id, {
			timeoutMs: 240_000,
			intervalMs: 1_500,
			minDocuments: 2,
		});

		await waitForDocumentByTitle(request, apiToken, searchSpace.id, FAKE_DRIVE_FILES.canary.name, {
			timeoutMs: 30_000,
		});
		await waitForDocumentByTitle(
			request,
			apiToken,
			searchSpace.id,
			FAKE_DRIVE_FILES.pdfNative.name,
			{ timeoutMs: 60_000 }
		);

		const docs = await listDocuments(request, apiToken, searchSpace.id);
		const canaryDoc = docs.find((d) => d.title === FAKE_DRIVE_FILES.canary.name);
		const pdfDoc = docs.find((d) => d.title === FAKE_DRIVE_FILES.pdfNative.name);

		expect(canaryDoc, "native Drive canary document must exist after indexing").toBeDefined();
		if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");
		expect(canaryDoc.document_type).toBe("GOOGLE_DRIVE_FILE");
		expect(pdfDoc, "native Drive PDF document must exist after indexing").toBeDefined();
		if (!pdfDoc) throw new Error("unreachable: pdfDoc asserted defined above");
		expect(pdfDoc.document_type).toBe("GOOGLE_DRIVE_FILE");

		const editor = await getEditorContent(request, apiToken, searchSpace.id, canaryDoc.id);
		expect(
			editor.source_markdown,
			`canary token ${CANARY_TOKENS.driveCanaryFile} should appear in editor source_markdown; ` +
				`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.driveCanaryFile);
		expect(editor.document_type).toBe("GOOGLE_DRIVE_FILE");
		expect(editor.chunk_count).toBeGreaterThan(0);

		const pdfEditor = await getEditorContent(request, apiToken, searchSpace.id, pdfDoc.id);
		expect(
			pdfEditor.source_markdown,
			`PDF canary token ${CANARY_TOKENS.drivePdfCanary} should appear in editor source_markdown; ` +
				`got first 200 chars: ${pdfEditor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.drivePdfCanary);
		expect(pdfEditor.document_type).toBe("GOOGLE_DRIVE_FILE");
		expect(pdfEditor.chunk_count).toBeGreaterThan(0);

		const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === nativeDriveConnector.id);
		expect(refreshed?.connector_type).toBe("GOOGLE_DRIVE_CONNECTOR");
		expect(refreshed?.is_indexable).toBe(true);
		expect(refreshed?.last_indexed_at).not.toBeNull();

		const chat = await streamChatToCompletion(request, apiToken, {
			searchSpaceId: searchSpace.id,
			threadId: chatThread.id,
			query: "What is in my e2e-canary.txt native Drive file?",
		});
		expect(
			chat.assistantText,
			`chat agent should surface native Drive canary token after indexing; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.driveCanaryFile);

		const pdfChat = await streamChatToCompletion(request, apiToken, {
			searchSpaceId: searchSpace.id,
			threadId: chatThread.id,
			query: "What is in my e2e-canary.pdf native Drive file?",
		});
		expect(
			pdfChat.assistantText,
			`chat agent should surface native Drive PDF canary token after indexing; got: ${pdfChat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.drivePdfCanary);
	});
});
