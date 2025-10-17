// Helper function to get connector type display name
export const getConnectorTypeDisplay = (type: string): string => {
	const typeMap: Record<string, string> = {
		SERPER_API: "Serper API",
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
		CLICKUP_CONNECTOR: "ClickUp",
		GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
		GOOGLE_GMAIL_CONNECTOR: "Google Gmail",
		AIRTABLE_CONNECTOR: "Airtable",
		LUMA_CONNECTOR: "Luma",
		ELASTICSEARCH_CONNECTOR: "Elasticsearch",
	};
	return typeMap[type] || type;
};
