// Helper function to get connector type display name
export const getConnectorTypeDisplay = (type: string): string => {
	const typeMap: Record<string, string> = {
		TAVILY_API: "Tavily API",
		SEARXNG_API: "SearxNG",
		SLACK_CONNECTOR: "Slack",
		NOTION_CONNECTOR: "Notion",
		GITHUB_CONNECTOR: "GitHub",
		LINEAR_CONNECTOR: "Linear",
		JIRA_CONNECTOR: "Jira",
		DISCORD_CONNECTOR: "Discord",
		LINKUP_API: "Linkup",
		CONFLUENCE_CONNECTOR: "Confluence",
		BOOKSTACK_CONNECTOR: "BookStack",
		CLICKUP_CONNECTOR: "ClickUp",
		GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
		GOOGLE_GMAIL_CONNECTOR: "Google Gmail",
		GOOGLE_DRIVE_CONNECTOR: "Google Drive",
		COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Google Drive",
		COMPOSIO_GMAIL_CONNECTOR: "Gmail",
		COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
		AIRTABLE_CONNECTOR: "Airtable",
		LUMA_CONNECTOR: "Luma",
		ELASTICSEARCH_CONNECTOR: "Elasticsearch",
		WEBCRAWLER_CONNECTOR: "Web Pages",
		CIRCLEBACK_CONNECTOR: "Circleback",
		OBSIDIAN_CONNECTOR: "Obsidian",
	};
	return typeMap[type] || type;
};
