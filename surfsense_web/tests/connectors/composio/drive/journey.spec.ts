import { expect, composioDriveWithChatTest as test } from "../../../fixtures";
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
 * Proves the Drive wiring from OAuth fixture -> selection persistence ->
 * indexing -> stored source_markdown -> editor-content retrieval -> chat.
 *
 * UI-driven file selection and LLM/embedding quality are
 * covered by later phases or narrower tests.
 */
test.describe("Composio Drive journey", () => {
	test("user connects Drive, selects a file, indexes it, and chats with the canary token", async ({
		page,
		request,
		apiToken,
		workspace,
		composioDriveConnector,
		chatThread,
	}) => {
		test.setTimeout(240_000); // worker cold-start + Docling + summarize + embed + chunk

		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
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
				id: FAKE_DRIVE_FILES.pdfComposio.id,
				name: FAKE_DRIVE_FILES.pdfComposio.name,
				mimeType: FAKE_DRIVE_FILES.pdfComposio.mimeType,
			},
		];
		const indexingOptions = {
			max_files_per_folder: 10,
			incremental_sync: false,
			include_subfolders: false,
		};

		await updateConnectorConfig(request, apiToken, composioDriveConnector.id, {
			...composioDriveConnector.config,
			selected_folders: [],
			selected_files: selectedFiles,
			indexing_options: indexingOptions,
		});

		await triggerIndex(request, apiToken, composioDriveConnector.id, workspace.id, {
			files: selectedFiles,
			indexing_options: indexingOptions,
		});

		await waitForIndexingComplete(request, apiToken, composioDriveConnector.id, workspace.id, {
			timeoutMs: 240_000,
			intervalMs: 1_500,
			minDocuments: 2,
		});

		await waitForDocumentByTitle(request, apiToken, workspace.id, FAKE_DRIVE_FILES.canary.name, {
			timeoutMs: 30_000,
		});
		await waitForDocumentByTitle(
			request,
			apiToken,
			workspace.id,
			FAKE_DRIVE_FILES.pdfComposio.name,
			{ timeoutMs: 60_000 }
		);

		const docs = await listDocuments(request, apiToken, workspace.id);
		const canaryDoc = docs.find((d) => d.title === FAKE_DRIVE_FILES.canary.name);
		const pdfDoc = docs.find((d) => d.title === FAKE_DRIVE_FILES.pdfComposio.name);

		expect(canaryDoc, "canary document must exist after indexing").toBeDefined();
		if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");
		expect(canaryDoc.document_type).toBe("GOOGLE_DRIVE_FILE");
		expect(pdfDoc, "Composio Drive PDF document must exist after indexing").toBeDefined();
		if (!pdfDoc) throw new Error("unreachable: pdfDoc asserted defined above");
		expect(pdfDoc.document_type).toBe("GOOGLE_DRIVE_FILE");

		// content holds the LLM summary; the raw file body lives in source_markdown.
		// editor-content is the same endpoint the UI hits when opening a document.
		const editor = await getEditorContent(request, apiToken, workspace.id, canaryDoc.id);
		expect(
			editor.source_markdown,
			`canary token ${CANARY_TOKENS.driveCanaryFile} should appear in editor source_markdown; ` +
				`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.driveCanaryFile);
		expect(editor.document_type).toBe("GOOGLE_DRIVE_FILE");
		expect(editor.chunk_count).toBeGreaterThan(0);

		const pdfEditor = await getEditorContent(request, apiToken, workspace.id, pdfDoc.id);
		expect(
			pdfEditor.source_markdown,
			`PDF canary token ${CANARY_TOKENS.composioDrivePdfCanary} should appear in editor source_markdown; ` +
				`got first 200 chars: ${pdfEditor.source_markdown.slice(0, 200)}`
		).toContain(CANARY_TOKENS.composioDrivePdfCanary);
		expect(pdfEditor.document_type).toBe("GOOGLE_DRIVE_FILE");
		expect(pdfEditor.chunk_count).toBeGreaterThan(0);

		const refreshedConnectors = await listConnectors(request, apiToken, workspace.id);
		const refreshed = refreshedConnectors.find((c) => c.id === composioDriveConnector.id);
		expect(refreshed?.last_indexed_at).not.toBeNull();

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: "What is in my e2e-canary.txt Drive file?",
		});
		expect(
			chat.assistantText,
			`chat agent should surface canary token after indexing; got: ${chat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.driveCanaryFile);

		const pdfChat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: chatThread.id,
			query: "What is in my e2e-composio-canary.pdf Drive file?",
		});
		expect(
			pdfChat.assistantText,
			`chat agent should surface Composio Drive PDF canary token after indexing; got: ${pdfChat.assistantText.slice(0, 200)}`
		).toContain(CANARY_TOKENS.composioDrivePdfCanary);
	});
});
