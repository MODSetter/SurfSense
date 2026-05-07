import { expect, nativeOneDriveWithChatTest as test } from "../../fixtures";
import { streamChatToCompletion } from "../../helpers/api/chat";
import {
	listConnectors,
	triggerIndex,
	updateConnectorConfig,
} from "../../helpers/api/connectors";
import { getEditorContent, listDocuments } from "../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_ONEDRIVE_FILES } from "../../helpers/canary";
import { openConnectorPopup } from "../../helpers/ui/connector-popup";
import {
	waitForDocumentByTitle,
	waitForIndexingComplete,
} from "../../helpers/waits/indexing";

/**
 * Proves the native OneDrive wiring from Microsoft OAuth fixture -> selection
 * persistence -> OneDrive Graph API indexing -> stored source_markdown -> chat.
 *
 * The folder picker is intentionally bypassed; this journey exercises the
 * persisted config and indexing contract the picker ultimately feeds.
 */
test.describe("Native OneDrive journey", () => {
	test(
		"user connects OneDrive, selects a file, indexes it, and chats with the canary token",
		async ({
			page,
			request,
			apiToken,
			searchSpace,
			nativeOneDriveConnector,
			chatThread,
		}) => {
			test.setTimeout(180_000); // worker cold-start + summarize + embed + chunk

			expect(nativeOneDriveConnector.connector_type).toBe("ONEDRIVE_CONNECTOR");
			expect(nativeOneDriveConnector.is_indexable).toBe(true);
			expect(nativeOneDriveConnector.config._token_encrypted).toBe(true);
			expect(nativeOneDriveConnector.config.composio_connected_account_id).toBeUndefined();

			await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
				waitUntil: "domcontentloaded",
			});
			await openConnectorPopup(page);
			const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
			await expect(connectorDialog).toBeVisible();

			const selectedFiles = [
				{
					id: FAKE_ONEDRIVE_FILES.canary.id,
					name: FAKE_ONEDRIVE_FILES.canary.name,
					mimeType: FAKE_ONEDRIVE_FILES.canary.mimeType,
				},
			];
			// Keep the shared Drive-style body shape. OneDrive currently defaults
			// these internally because the indexer expects max_files/use_delta_sync.
			const indexingOptions = {
				max_files_per_folder: 10,
				incremental_sync: false,
				include_subfolders: false,
			};

			await updateConnectorConfig(request, apiToken, nativeOneDriveConnector.id, {
				...nativeOneDriveConnector.config,
				selected_folders: [],
				selected_files: selectedFiles,
				indexing_options: indexingOptions,
			});

			await triggerIndex(request, apiToken, nativeOneDriveConnector.id, searchSpace.id, {
				files: selectedFiles,
				indexing_options: indexingOptions,
			});

			await waitForIndexingComplete(
				request,
				apiToken,
				nativeOneDriveConnector.id,
				searchSpace.id,
				{
					timeoutMs: 150_000,
					intervalMs: 1_500,
					minDocuments: 1,
				}
			);

			await waitForDocumentByTitle(
				request,
				apiToken,
				searchSpace.id,
				FAKE_ONEDRIVE_FILES.canary.name,
				{ timeoutMs: 30_000 }
			);

			const docs = await listDocuments(request, apiToken, searchSpace.id);
			const canaryDoc = docs.find((d) => d.title === FAKE_ONEDRIVE_FILES.canary.name);

			expect(canaryDoc, "OneDrive canary document must exist after indexing").toBeDefined();
			if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");
			expect(canaryDoc.document_type).toBe("ONEDRIVE_FILE");

			const editor = await getEditorContent(request, apiToken, searchSpace.id, canaryDoc.id);
			expect(
				editor.source_markdown,
				`canary token ${CANARY_TOKENS.onedriveCanary} should appear in editor source_markdown; ` +
					`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
			).toContain(CANARY_TOKENS.onedriveCanary);
			expect(editor.document_type).toBe("ONEDRIVE_FILE");
			expect(editor.chunk_count).toBeGreaterThan(0);

			const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
			const refreshed = refreshedConnectors.find((c) => c.id === nativeOneDriveConnector.id);
			expect(refreshed?.connector_type).toBe("ONEDRIVE_CONNECTOR");
			expect(refreshed?.is_indexable).toBe(true);
			expect(refreshed?.last_indexed_at).not.toBeNull();

			const chat = await streamChatToCompletion(request, apiToken, {
				searchSpaceId: searchSpace.id,
				threadId: chatThread.id,
				query: "What is in my e2e-onedrive-canary.txt OneDrive file?",
			});
			expect(
				chat.assistantText,
				"chat agent should surface OneDrive canary token after indexing; " +
					`got: ${chat.assistantText.slice(0, 200)}`
			).toContain(CANARY_TOKENS.onedriveCanary);
		}
	);
});
