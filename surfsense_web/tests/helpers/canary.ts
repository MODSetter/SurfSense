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
	gmailCanary: "SURFSENSE_E2E_CANARY_TOKEN_GMAIL_001",
	calendarCanary: "SURFSENSE_E2E_CANARY_TOKEN_CALENDAR_001",
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

/**
 * Fake Gmail message IDs that match what the backend fake returns from
 * GMAIL_FETCH_EMAILS / GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID.
 */
export const FAKE_GMAIL_MESSAGES = {
	canary: {
		id: "fake-msg-canary-001",
		threadId: "fake-thread-canary-001",
		subject: "E2E Canary Email",
		from: "sender@surfsense.example",
		to: "e2e-fake@surfsense.example",
	},
	planning: {
		id: "fake-msg-planning-001",
		threadId: "fake-thread-planning-001",
		subject: "E2E Planning Notes",
		from: "planner@surfsense.example",
		to: "e2e-fake@surfsense.example",
	},
} as const;

/**
 * Fake Calendar event IDs that match what the backend fake returns from
 * GOOGLECALENDAR_EVENTS_LIST.
 */
export const FAKE_CALENDAR_EVENTS = {
	canary: {
		id: "fake-calendar-event-canary-001",
		summary: "E2E Canary Calendar Event",
		location: "SurfSense E2E Room",
	},
	planning: {
		id: "fake-calendar-event-planning-001",
		summary: "E2E Planning Sync",
		location: "SurfSense Planning Room",
	},
} as const;

/** Generate a unique-per-run search space name. Keeps parallel tests isolated. */
export function uniqueSearchSpaceName(prefix = "e2e"): string {
	return `${prefix}-${randomUUID().slice(0, 8)}`;
}
