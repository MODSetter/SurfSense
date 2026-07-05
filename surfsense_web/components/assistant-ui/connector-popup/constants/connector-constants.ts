import { EnumConnectorName } from "@/contracts/enums/connector";

/**
 * Connectors retired during the MCP migration (no viable official MCP server).
 * The catalog card is shown disabled with a "Deprecated" badge so existing
 * users understand why; the backend `/add` routes also refuse with HTTP 410.
 * Reinstate by removing the type here and in the backend
 * `DEPRECATED_CONNECTOR_TYPES` if demand returns.
 */
export const DEPRECATED_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.DISCORD_CONNECTOR,
	EnumConnectorName.TEAMS_CONNECTOR,
	EnumConnectorName.LUMA_CONNECTOR,
	// Search APIs retired by the Google-only web-search consolidation. Public
	// web search now runs through the google_search subagent; Tavily/Linkup can
	// still be added via the generic Custom MCP connector (API-key headers).
	EnumConnectorName.TAVILY_API,
	EnumConnectorName.SEARXNG_API,
	EnumConnectorName.LINKUP_API,
	EnumConnectorName.BAIDU_SEARCH_API,
]);

/**
 * Connectors that operate in real time (no background indexing).
 * Used to adjust UI: hide sync controls, show "Connected" instead of doc counts.
 */
export const LIVE_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.LINEAR_CONNECTOR,
	EnumConnectorName.SLACK_CONNECTOR,
	EnumConnectorName.JIRA_CONNECTOR,
	EnumConnectorName.CLICKUP_CONNECTOR,
	EnumConnectorName.AIRTABLE_CONNECTOR,
	EnumConnectorName.DISCORD_CONNECTOR,
	EnumConnectorName.TEAMS_CONNECTOR,
	EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR,
	EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
	EnumConnectorName.GOOGLE_GMAIL_CONNECTOR,
	EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR,
	EnumConnectorName.LUMA_CONNECTOR,
	// Migrated to hosted MCP: real-time agent tools, no background indexing.
	EnumConnectorName.NOTION_CONNECTOR,
	EnumConnectorName.CONFLUENCE_CONNECTOR,
]);

// OAuth Connectors (Quick Connect)
export const OAUTH_CONNECTORS = [
	{
		id: "google-drive-connector",
		title: "Google Drive",
		description: "Search your Drive files",
		connectorType: EnumConnectorName.GOOGLE_DRIVE_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/drive/connector/add/",
		selfHostedOnly: true,
	},
	{
		id: "google-gmail-connector",
		title: "Gmail",
		description: "Search, read, draft, and send emails",
		connectorType: EnumConnectorName.GOOGLE_GMAIL_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/gmail/connector/add/",
		selfHostedOnly: true,
	},
	{
		id: "google-calendar-connector",
		title: "Google Calendar",
		description: "Search and manage your events",
		connectorType: EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/calendar/connector/add/",
		selfHostedOnly: true,
	},
	{
		id: "airtable-connector",
		title: "Airtable",
		description: "Browse bases, tables, and records",
		connectorType: EnumConnectorName.AIRTABLE_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/airtable/connector/add/",
	},
	{
		id: "notion-connector",
		title: "Notion",
		description: "Search, read, and create pages",
		connectorType: EnumConnectorName.NOTION_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/notion/connector/add/",
	},
	{
		id: "linear-connector",
		title: "Linear",
		description: "Search, read, and manage issues & projects",
		connectorType: EnumConnectorName.LINEAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/linear/connector/add/",
	},
	{
		id: "slack-connector",
		title: "Slack",
		description: "Search and read channels and threads",
		connectorType: EnumConnectorName.SLACK_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/slack/connector/add/",
	},
	{
		id: "teams-connector",
		title: "Microsoft Teams",
		description: "Search, read, and send messages",
		connectorType: EnumConnectorName.TEAMS_CONNECTOR,
		authEndpoint: "/api/v1/auth/teams/connector/add/",
	},
	{
		id: "onedrive-connector",
		title: "OneDrive",
		description: "Search your OneDrive files",
		connectorType: EnumConnectorName.ONEDRIVE_CONNECTOR,
		authEndpoint: "/api/v1/auth/onedrive/connector/add/",
	},
	{
		id: "dropbox-connector",
		title: "Dropbox",
		description: "Search your Dropbox files",
		connectorType: EnumConnectorName.DROPBOX_CONNECTOR,
		authEndpoint: "/api/v1/auth/dropbox/connector/add/",
	},
	{
		id: "discord-connector",
		title: "Discord",
		description: "Search, read, and send messages",
		connectorType: EnumConnectorName.DISCORD_CONNECTOR,
		authEndpoint: "/api/v1/auth/discord/connector/add/",
	},
	{
		id: "jira-connector",
		title: "Jira",
		description: "Search, read, and manage issues",
		connectorType: EnumConnectorName.JIRA_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/jira/connector/add/",
	},
	{
		id: "confluence-connector",
		title: "Confluence",
		description: "Search, read, and create pages",
		connectorType: EnumConnectorName.CONFLUENCE_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/confluence/connector/add/",
	},
	{
		id: "clickup-connector",
		title: "ClickUp",
		description: "Search and read tasks",
		connectorType: EnumConnectorName.CLICKUP_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/clickup/connector/add/",
	},
] as const;

// Content Sources (tools that extract and import content from external sources)
export const CRAWLERS = [
	{
		id: "youtube-crawler",
		title: "YouTube",
		description: "Crawl YouTube channels and playlists",
		connectorType: EnumConnectorName.YOUTUBE_CONNECTOR,
	},
	{
		id: "webcrawler-connector",
		title: "Web Pages",
		description: "Index and periodically sync web content",
		connectorType: EnumConnectorName.WEBCRAWLER_CONNECTOR,
	},
] as const;

// Non-OAuth Connectors (redirect to old connector config pages)
export const OTHER_CONNECTORS = [
	{
		id: "bookstack-connector",
		title: "BookStack",
		description: "Search BookStack docs",
		connectorType: EnumConnectorName.BOOKSTACK_CONNECTOR,
	},
	{
		id: "github-connector",
		title: "GitHub",
		description: "Search repositories",
		connectorType: EnumConnectorName.GITHUB_CONNECTOR,
	},
	{
		id: "luma-connector",
		title: "Luma",
		description: "Browse, read, and create events",
		connectorType: EnumConnectorName.LUMA_CONNECTOR,
	},
	{
		id: "elasticsearch-connector",
		title: "Elasticsearch",
		description: "Search ES indexes",
		connectorType: EnumConnectorName.ELASTICSEARCH_CONNECTOR,
	},
	{
		id: "tavily-api",
		title: "Tavily AI",
		description: "Search with Tavily",
		connectorType: EnumConnectorName.TAVILY_API,
	},
	{
		id: "linkup-api",
		title: "Linkup API",
		description: "Search with Linkup",
		connectorType: EnumConnectorName.LINKUP_API,
	},
	{
		id: "baidu-search-api",
		title: "Baidu Search",
		description: "Search with Baidu",
		connectorType: EnumConnectorName.BAIDU_SEARCH_API,
	},
	{
		id: "circleback-connector",
		title: "Circleback",
		description: "Receive meeting notes, transcripts",
		connectorType: EnumConnectorName.CIRCLEBACK_CONNECTOR,
	},
	{
		id: "mcp-connector",
		title: "MCPs",
		description: "Connect to MCP servers for AI tools",
		connectorType: EnumConnectorName.MCP_CONNECTOR,
	},
	{
		id: "obsidian-connector",
		title: "Obsidian",
		description: "Sync your Obsidian vault on desktop or mobile",
		connectorType: EnumConnectorName.OBSIDIAN_CONNECTOR,
	},
] as const;

// Composio Connectors - Individual entries for each supported toolkit
export const COMPOSIO_CONNECTORS = [
	{
		id: "composio-googledrive",
		title: "Google Drive",
		description: "Search your Drive files via Composio",
		connectorType: EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
		authEndpoint: "/api/v1/auth/composio/connector/add/?toolkit_id=googledrive",
	},
	{
		id: "composio-gmail",
		title: "Gmail",
		description: "Search, read, draft, and send emails via Composio",
		connectorType: EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR,
		authEndpoint: "/api/v1/auth/composio/connector/add/?toolkit_id=gmail",
	},
	{
		id: "composio-googlecalendar",
		title: "Google Calendar",
		description: "Search and manage your events via Composio",
		connectorType: EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/composio/connector/add/?toolkit_id=googlecalendar",
	},
] as const;

export const CONNECTOR_DISPLAY_DEFINITIONS = [
	...OAUTH_CONNECTORS,
	...CRAWLERS,
	...OTHER_CONNECTORS,
	...COMPOSIO_CONNECTORS,
] as const;

export function getConnectorTitle(connectorType: string): string {
	return (
		CONNECTOR_DISPLAY_DEFINITIONS.find((connector) => connector.connectorType === connectorType)
			?.title ?? connectorType
	);
}

/**
 * Primary way a user interacts with a connector.
 * Drives the two top-level groupings in the connector catalog UI.
 */
export type ConnectorCategory = "knowledge_base" | "tools_live";

export const CONNECTOR_CATEGORY_LABELS: Record<ConnectorCategory, string> = {
	knowledge_base: "Knowledge Base",
	tools_live: "Tools & Live Sources",
};

const KNOWLEDGE_BASE_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.ONEDRIVE_CONNECTOR,
	EnumConnectorName.DROPBOX_CONNECTOR,
	EnumConnectorName.NOTION_CONNECTOR,
	EnumConnectorName.CONFLUENCE_CONNECTOR,
	EnumConnectorName.YOUTUBE_CONNECTOR,
	EnumConnectorName.WEBCRAWLER_CONNECTOR,
	EnumConnectorName.BOOKSTACK_CONNECTOR,
	EnumConnectorName.GITHUB_CONNECTOR,
	EnumConnectorName.ELASTICSEARCH_CONNECTOR,
	EnumConnectorName.CIRCLEBACK_CONNECTOR,
	EnumConnectorName.OBSIDIAN_CONNECTOR,
]);

/** Unmapped connectors surface under Tools & Live Sources. */
export function getConnectorCategory(connectorType: string): ConnectorCategory {
	return KNOWLEDGE_BASE_CONNECTOR_TYPES.has(connectorType) ? "knowledge_base" : "tools_live";
}

// Composio Toolkits (available integrations via Composio)
export const COMPOSIO_TOOLKITS = [
	{
		id: "googledrive",
		name: "Google Drive",
		description: "Search your Drive files",
		isIndexable: true,
	},
	{
		id: "gmail",
		name: "Gmail",
		description: "Search, read, draft, and send emails",
		isIndexable: false,
	},
	{
		id: "googlecalendar",
		name: "Google Calendar",
		description: "Search and manage your events",
		isIndexable: false,
	},
	{
		id: "slack",
		name: "Slack",
		description: "Search Slack messages",
		isIndexable: false,
	},
	{
		id: "notion",
		name: "Notion",
		description: "Search Notion pages",
		isIndexable: false,
	},
	{
		id: "github",
		name: "GitHub",
		description: "Search repositories",
		isIndexable: false,
	},
] as const;

export interface AutoIndexConfig {
	daysBack: number;
	daysForward: number;
	frequencyMinutes: number;
	syncDescription: string;
}

export const AUTO_INDEX_DEFAULTS: Record<string, AutoIndexConfig> = {
	[EnumConnectorName.NOTION_CONNECTOR]: {
		daysBack: 365,
		daysForward: 0,
		frequencyMinutes: 1440,
		syncDescription: "Syncing your pages.",
	},
	[EnumConnectorName.CONFLUENCE_CONNECTOR]: {
		daysBack: 365,
		daysForward: 0,
		frequencyMinutes: 1440,
		syncDescription: "Syncing your documentation.",
	},
};

export const AUTO_INDEX_CONNECTOR_TYPES = new Set<string>(Object.keys(AUTO_INDEX_DEFAULTS));

// Re-export IndexingConfigState from schemas for backward compatibility
export type { IndexingConfigState } from "./connector-popup.schemas";
