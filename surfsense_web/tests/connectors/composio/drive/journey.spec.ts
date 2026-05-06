import { composioDriveTest as test, expect } from "../../../fixtures";
import { listConnectors, triggerIndex, updateConnectorConfig } from "../../../helpers/api/connectors";
import { listDocuments } from "../../../helpers/api/documents";
import { CANARY_TOKENS, FAKE_DRIVE_FILES } from "../../../helpers/canary";
import { openConnectorPopup } from "../../../helpers/ui/connector-popup";
import {
	waitForDocumentByTitle,
	waitForIndexingComplete,
} from "../../../helpers/waits/indexing";

/**
 * Composio Drive user journey.
 *
 * User expectation:
 *   "I connect Google Drive, choose the files/folders I care about,
 *    wait for indexing, and then my Drive content is available in SurfSense."
 *
 * The OAuth connection is handled by the composioDriveConnector fixture so
 * this test can focus on the user-visible expectation. The spec still touches
 * the browser (dashboard + connector dialog) and then uses API helpers for
 * selection/indexing to keep the expensive pipeline assertion deterministic.
 *
 * If this passes, the seam from Composio connection -> selection persistence ->
 * Celery indexing -> document storage is wired correctly.
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
			await expect(
				page
					.getByRole("dialog", { name: "Manage Connectors" })
					.getByText("Search your Drive files via Composio")
			).toBeVisible();

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

			const content = canaryDoc!.content ?? "";
			expect(
				content,
				`canary token ${CANARY_TOKENS.driveCanaryFile} should appear in Document.content; ` +
					`got first 200 chars: ${content.slice(0, 200)}`
			).toContain(CANARY_TOKENS.driveCanaryFile);

			const refreshedConnectors = await listConnectors(request, apiToken, searchSpace.id);
			const refreshed = refreshedConnectors.find((c) => c.id === composioDriveConnector.id);
			expect(refreshed?.last_indexed_at).not.toBeNull();
		}
	);
});
