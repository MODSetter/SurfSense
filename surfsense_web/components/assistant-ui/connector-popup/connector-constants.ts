import { EnumConnectorName } from "@/contracts/enums/connector";

// OAuth Connectors (Quick Connect)
export const OAUTH_CONNECTORS = [
	{
		id: "google-gmail-connector",
		title: "Gmail",
		description: "Search through your emails",
		connectorType: EnumConnectorName.GOOGLE_GMAIL_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/gmail/connector/add/",
	},
	{
		id: "google-calendar-connector",
		title: "Google Calendar",
		description: "Search through your events",
		connectorType: EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/calendar/connector/add/",
	},
	{
		id: "airtable-connector",
		title: "Airtable",
		description: "Search your Airtable bases",
		connectorType: EnumConnectorName.AIRTABLE_CONNECTOR,
		authEndpoint: "/api/v1/auth/airtable/connector/add/",
	},
] as const;

// Non-OAuth Connectors
export const OTHER_CONNECTORS = [
	{
		id: "slack-connector",
		title: "Slack",
		description: "Search Slack messages",
		connectorType: EnumConnectorName.SLACK_CONNECTOR,
	},
	{
		id: "discord-connector",
		title: "Discord",
		description: "Search Discord messages",
		connectorType: EnumConnectorName.DISCORD_CONNECTOR,
	},
	{
		id: "notion-connector",
		title: "Notion",
		description: "Search Notion pages",
		connectorType: EnumConnectorName.NOTION_CONNECTOR,
	},
	{
		id: "confluence-connector",
		title: "Confluence",
		description: "Search documentation",
		connectorType: EnumConnectorName.CONFLUENCE_CONNECTOR,
	},
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
		id: "linear-connector",
		title: "Linear",
		description: "Search issues & projects",
		connectorType: EnumConnectorName.LINEAR_CONNECTOR,
	},
	{
		id: "jira-connector",
		title: "Jira",
		description: "Search Jira issues",
		connectorType: EnumConnectorName.JIRA_CONNECTOR,
	},
	{
		id: "clickup-connector",
		title: "ClickUp",
		description: "Search ClickUp tasks",
		connectorType: EnumConnectorName.CLICKUP_CONNECTOR,
	},
	{
		id: "luma-connector",
		title: "Luma",
		description: "Search Luma events",
		connectorType: EnumConnectorName.LUMA_CONNECTOR,
	},
	{
		id: "elasticsearch-connector",
		title: "Elasticsearch",
		description: "Search ES indexes",
		connectorType: EnumConnectorName.ELASTICSEARCH_CONNECTOR,
	},
	{
		id: "webcrawler-connector",
		title: "Web Pages",
		description: "Crawl web content",
		connectorType: EnumConnectorName.WEBCRAWLER_CONNECTOR,
	},
	{
		id: "tavily-api",
		title: "Tavily AI",
		description: "Search with Tavily",
		connectorType: EnumConnectorName.TAVILY_API,
	},
	{
		id: "searxng",
		title: "SearxNG",
		description: "Search with SearxNG",
		connectorType: EnumConnectorName.SEARXNG_API,
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
] as const;

// Type for the indexing configuration state
export interface IndexingConfigState {
	connectorType: string;
	connectorId: number;
	connectorTitle: string;
}

