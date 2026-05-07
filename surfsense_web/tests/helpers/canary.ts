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
	notionCanary: "SURFSENSE_E2E_CANARY_TOKEN_NOTION_001",
	confluenceCanary: "SURFSENSE_E2E_CANARY_TOKEN_CONFLUENCE_001",
	linearCanary: "SURFSENSE_E2E_CANARY_TOKEN_LINEAR_001",
	jiraCanary: "SURFSENSE_E2E_CANARY_TOKEN_JIRA_001",
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

/**
 * Fake Notion page IDs that match what the backend fake returns from
 * notion_client.AsyncClient.search.
 */
export const FAKE_NOTION_PAGES = {
	canary: {
		id: "fake-notion-page-canary-001",
		title: "E2E Canary Notion Page",
		workspaceId: "fake-notion-workspace-001",
		workspaceName: "SurfSense E2E Notion Workspace",
		botId: "fake-notion-bot-001",
	},
} as const;

/**
 * Fake Confluence page IDs that match what the backend fake returns from
 * ConfluenceHistoryConnector.get_pages_by_date_range.
 */
export const FAKE_CONFLUENCE_PAGES = {
	canary: {
		id: "fake-confluence-page-canary-001",
		title: "E2E Canary Confluence Page",
		spaceId: "fake-confluence-space-001",
		cloudId: "fake-confluence-cloud-001",
		baseUrl: "https://surfsense-e2e-confluence.atlassian.net",
	},
} as const;

/**
 * Fake Linear issue IDs that match what the backend MCP fake returns from
 * list_issues / get_issue.
 */
export const FAKE_LINEAR_ISSUES = {
	canary: {
		id: "fake-linear-issue-canary-001",
		identifier: "E2E-101",
		title: "E2E Canary Linear Issue",
		organizationName: "SurfSense E2E Linear Org",
		organizationUrlKey: "surfsense-e2e",
	},
} as const;

/**
 * Fake Jira issue IDs that match what the backend MCP fake returns from
 * searchJiraIssuesUsingJql.
 */
export const FAKE_JIRA_ISSUES = {
	canary: {
		id: "fake-jira-issue-canary-001",
		key: "E2E-101",
		summary: "E2E Canary Jira Issue",
		cloudId: "fake-jira-cloud-001",
		siteUrl: "https://surfsense-e2e.atlassian.net",
	},
} as const;

/** Generate a unique-per-run search space name. Keeps parallel tests isolated. */
export function uniqueSearchSpaceName(prefix = "e2e"): string {
	return `${prefix}-${randomUUID().slice(0, 8)}`;
}
