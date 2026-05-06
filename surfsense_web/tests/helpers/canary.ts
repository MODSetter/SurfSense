import { randomUUID } from "node:crypto";

/**
 * Canary tokens & deterministic test data.
 *
 * Embedded by the backend Composio fake into fake Drive file contents
 * (see surfsense_backend/tests/e2e/fakes/fixtures/drive_files.json).
 * Specs assert these strings appear in the resulting Document rows to
 * prove the indexing pipeline ran end-to-end.
 *
 * Each token is a stable string keyed by file id so multi-test runs
 * remain deterministic and the resulting Document.content is greppable
 * in failure traces.
 */
export const CANARY_TOKENS = {
	driveCanaryFile: "SURFSENSE_E2E_CANARY_TOKEN_DRIVE_001",
	driveReadme: "SURFSENSE_E2E_README_MARKER",
	driveBudget: "SURFSENSE_E2E_BUDGET_MARKER",
	driveRoadmap: "SURFSENSE_E2E_ROADMAP_MARKER",
	driveArchive: "SURFSENSE_E2E_ARCHIVE_MARKER",
} as const;

/**
 * Fake Drive file IDs that match what the backend fake returns from
 * GOOGLEDRIVE_LIST_FILES. Keep in sync with drive_files.json.
 */
export const FAKE_DRIVE_FILES = {
	canary: { id: "fake-file-canary", name: "e2e-canary.txt", mimeType: "text/plain" },
	readme: { id: "fake-file-readme", name: "README.md", mimeType: "text/markdown" },
	budget: { id: "fake-file-budget", name: "Q1-Budget.csv", mimeType: "text/csv" },
} as const;

export const FAKE_DRIVE_FOLDERS = {
	projects: {
		id: "fake-folder-projects",
		name: "Projects",
		mimeType: "application/vnd.google-apps.folder",
	},
	archive: {
		id: "fake-folder-archive",
		name: "Archive",
		mimeType: "application/vnd.google-apps.folder",
	},
} as const;

/** Generate a unique-per-run search space name. Keeps parallel tests isolated. */
export function uniqueSearchSpaceName(prefix = "e2e"): string {
	return `${prefix}-${randomUUID().slice(0, 8)}`;
}
