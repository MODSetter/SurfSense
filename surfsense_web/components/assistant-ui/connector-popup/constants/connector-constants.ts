import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

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
		description: "Search your Notion pages",
		connectorType: EnumConnectorName.NOTION_CONNECTOR,
		authEndpoint: "/api/v1/auth/notion/connector/add",
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
		description: "Search documentation",
		connectorType: EnumConnectorName.CONFLUENCE_CONNECTOR,
		authEndpoint: "/api/v1/auth/confluence/connector/add/",
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
		description: "Index your Obsidian vault (Local folder scan on Desktop)",
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

// ============================================================================
// CONNECTOR TELEMETRY REGISTRY
// ----------------------------------------------------------------------------
// Single source of truth for "what does this connector_type look like in
// analytics?". Any connector added to the lists above is automatically
// picked up here, so adding a new integration does NOT require touching
// `lib/posthog/events.ts` or per-connector tracking code.
// ============================================================================

export type ConnectorTelemetryGroup = "oauth" | "composio" | "crawler" | "other" | "unknown";

export interface ConnectorTelemetryMeta {
	connector_type: string;
	connector_title: string;
	connector_group: ConnectorTelemetryGroup;
	is_oauth: boolean;
}

const CONNECTOR_TELEMETRY_REGISTRY: ReadonlyMap<string, ConnectorTelemetryMeta> = (() => {
	const map = new Map<string, ConnectorTelemetryMeta>();

	for (const c of OAUTH_CONNECTORS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "oauth",
			is_oauth: true,
		});
	}
	for (const c of COMPOSIO_CONNECTORS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "composio",
			is_oauth: true,
		});
	}
	for (const c of CRAWLERS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "crawler",
			is_oauth: false,
		});
	}
	for (const c of OTHER_CONNECTORS) {
		map.set(c.connectorType, {
			connector_type: c.connectorType,
			connector_title: c.title,
			connector_group: "other",
			is_oauth: false,
		});
	}

	return map;
})();

/**
 * Returns telemetry metadata for a connector_type, or a minimal "unknown"
 * record so tracking never no-ops for connectors that exist in the backend
 * but were forgotten in the UI registry.
 */
export function getConnectorTelemetryMeta(connectorType: string): ConnectorTelemetryMeta {
	const hit = CONNECTOR_TELEMETRY_REGISTRY.get(connectorType);
	if (hit) return hit;

	return {
		connector_type: connectorType,
		connector_title: connectorType,
		connector_group: "unknown",
		is_oauth: false,
	};
}

// =============================================================================
// REAUTH ENDPOINTS
// =============================================================================

/**
 * Legacy (non-MCP) OAuth reauth endpoints, keyed by connector type.
 * These are used for connectors that were NOT created via MCP OAuth.
 */
export const LEGACY_REAUTH_ENDPOINTS: Partial<Record<string, string>> = {
	[EnumConnectorName.LINEAR_CONNECTOR]: "/api/v1/auth/linear/connector/reauth",
	[EnumConnectorName.JIRA_CONNECTOR]: "/api/v1/auth/jira/connector/reauth",
	[EnumConnectorName.NOTION_CONNECTOR]: "/api/v1/auth/notion/connector/reauth",
	[EnumConnectorName.GOOGLE_DRIVE_CONNECTOR]: "/api/v1/auth/google/drive/connector/reauth",
	[EnumConnectorName.GOOGLE_GMAIL_CONNECTOR]: "/api/v1/auth/google/gmail/connector/reauth",
	[EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR]: "/api/v1/auth/google/calendar/connector/reauth",
	[EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR]: "/api/v1/auth/composio/connector/reauth",
	[EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR]: "/api/v1/auth/composio/connector/reauth",
	[EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR]: "/api/v1/auth/composio/connector/reauth",
	[EnumConnectorName.ONEDRIVE_CONNECTOR]: "/api/v1/auth/onedrive/connector/reauth",
	[EnumConnectorName.DROPBOX_CONNECTOR]: "/api/v1/auth/dropbox/connector/reauth",
	[EnumConnectorName.CONFLUENCE_CONNECTOR]: "/api/v1/auth/confluence/connector/reauth",
	[EnumConnectorName.TEAMS_CONNECTOR]: "/api/v1/auth/teams/connector/reauth",
	[EnumConnectorName.DISCORD_CONNECTOR]: "/api/v1/auth/discord/connector/reauth",
};

/**
 * Resolve the reauth endpoint for a connector.
 *
 * MCP OAuth connectors (those with ``config.mcp_service``) dynamically build
 * the URL from the service key. Legacy OAuth connectors fall back to the
 * static ``LEGACY_REAUTH_ENDPOINTS`` map.
 */
export function getReauthEndpoint(connector: SearchSourceConnector): string | undefined {
	const mcpService = connector.config?.mcp_service as string | undefined;
	if (mcpService) {
		return `/api/v1/auth/mcp/${mcpService}/connector/reauth`;
	}
	return LEGACY_REAUTH_ENDPOINTS[connector.connector_type];
}

// Re-export IndexingConfigState from schemas for backward compatibility
export type { IndexingConfigState } from "./connector-popup.schemas";
