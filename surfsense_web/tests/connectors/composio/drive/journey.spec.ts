import { composioDriveTest as test, expect } from "../../../fixtures";
import { listConnectors, triggerIndex, updateConnectorConfig } from "../../../helpers/api/connectors";
import { getEditorContent, listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_DRIVE_FILES } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";
import {
	waitForDocumentByTitle,
	waitForIndexingComplete,
} from "../../../helpers/waits/indexing";

/**
 * Proves the Drive wiring from OAuth fixture -> selection persistence ->
 * indexing -> stored source_markdown -> editor-content retrieval.
 *
 * UI-driven file selection, chat retrieval, and LLM/embedding quality are
 * covered by later phases or narrower tests.
 */
test.describe("Composio Drive journey", () => {
	test(
		"user connects Drive, selects a file, and sees it indexed with the canary token",
		async ({ page, request, apiToken, searchSpace, composioDriveConnector }) => {
			test.setTimeout(180_000); // worker cold-start + summarize + embed + chunk

			await page.goto(`/dashboard/${searchSpace.id}/new-chat`, {
				waitUntil: "domcontentloaded",
			});
			await openConnectorPopup(page);
			const connectorDialog = page.getByRole("dialog", { name: "Manage Connectors" });
			await expect(connectorDialog).toBeVisible();
			await expect(connectorDialog.getByRole("button", { name: "Manage" })).toBeVisible();

			await updateConnectorConfig(request, apiToken, composioDriveConnector.id, {
				...composioDriveConnector.config,
				selected_folders: [],
				selected_files: [
					{
						id: FAKE_DRIVE_FILES.canary.id,
						name: FAKE_DRIVE_FILES.canary.name,
						mimeType: FAKE_DRIVE_FILES.canary.mimeType,
					},
				],
				indexing_options: {
					max_files_per_folder: 10,
					incremental_sync: false,
					include_subfolders: false,
				},
			});

			await triggerIndex(request, apiToken, composioDriveConnector.id, searchSpace.id, {
				files: [
					{
						id: FAKE_DRIVE_FILES.canary.id,
						name: FAKE_DRIVE_FILES.canary.name,
						mimeType: FAKE_DRIVE_FILES.canary.mimeType,
					},
				],
				indexing_options: {
					max_files_per_folder: 10,
					incremental_sync: false,
					include_subfolders: false,
				},
			});

			await waitForIndexingComplete(request, apiToken, composioDriveConnector.id, searchSpace.id, {
				timeoutMs: 150_000,
				intervalMs: 1_500,
				minDocuments: 1,
			});

			await waitForDocumentByTitle(
				request,
				apiToken,
				searchSpace.id,
				FAKE_DRIVE_FILES.canary.name,
				{ timeoutMs: 30_000 }
			);

			const docs = await listDocuments(request, apiToken, searchSpace.id);
			const canaryDoc = docs.find((d) => d.title === FAKE_DRIVE_FILES.canary.name);

			expect(canaryDoc, "canary document must exist after indexing").toBeDefined();
			if (!canaryDoc) throw new Error("unreachable: canaryDoc asserted defined above");

			// content holds the LLM summary; the raw file body lives in source_markdown.
			// editor-content is the same endpoint the UI hits when opening a document.
			const editor = await getEditorContent(request, apiToken, searchSpace.id, canaryDoc.id);
			expect(
				editor.source_markdown,
				`canary token ${CANARY_TOKENS.driveCanaryFile} should appear in editor source_markdown; ` +
					`got first 200 chars: ${editor.source_markdown.slice(0, 200)}`
			).toContain(CANARY_TOKENS.driveCanaryFile);
			expect(editor.chunk_count).toBeGreaterThan(0);

			const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
			const refreshed = refreshedConnectors.find((c) => c.id === composioDriveConnector.id);
			expect(refreshed?.last_indexed_at).not.toBeNull();
		}
	);
});
