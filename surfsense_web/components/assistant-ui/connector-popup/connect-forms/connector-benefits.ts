/**
 * Helper function to get connector-specific benefits list
 * Returns null if no benefits are defined for the connector
 */
export function getConnectorBenefits(connectorType: string): string[] | null {
	const benefits: Record<string, string[]> = {
		LINEAR_CONNECTOR: [
			"Search through all your Linear issues and comments",
			"Access issue titles, descriptions, and full discussion threads",
			"Connect your team's project management directly to your search space",
			"Keep your search results up-to-date with latest Linear content",
			"Index your Linear issues for enhanced search capabilities",
		],
		ELASTICSEARCH_CONNECTOR: [
			"Search across your indexed documents and logs",
			"Access structured and unstructured data from your cluster",
			"Leverage existing Elasticsearch indices for enhanced search",
			"Real-time search capabilities with powerful query features",
			"Integration with your existing Elasticsearch infrastructure",
		],
		TAVILY_API: [
			"AI-powered search results tailored to your queries",
			"Real-time information from the web",
			"Enhanced search capabilities for your projects",
		],
		SEARXNG_API: [
			"Privacy-focused meta-search across multiple engines",
			"Self-hosted search instance for full control",
			"Real-time web search results from multiple sources",
		],
		LINKUP_API: [
			"AI-powered search results tailored to your queries",
			"Real-time information from the web",
			"Enhanced search capabilities for your projects",
		],
		BAIDU_SEARCH_API: [
			"Intelligent search tailored for Chinese web content",
			"Real-time information from Baidu's search index",
			"AI-powered summarization with source references",
		],
		SLACK_CONNECTOR: [
			"Search through all your Slack messages and conversations",
			"Access messages from public and private channels",
			"Connect your team's communications directly to your search space",
			"Keep your search results up-to-date with latest Slack content",
			"Index your Slack conversations for enhanced search capabilities",
		],
		DISCORD_CONNECTOR: [
			"Search through all your Discord messages and conversations",
			"Access messages from all accessible channels",
			"Connect your community's communications directly to your search space",
			"Keep your search results up-to-date with latest Discord content",
			"Index your Discord conversations for enhanced search capabilities",
		],
		NOTION_CONNECTOR: [
			"Search through all your Notion pages and databases",
			"Access page content, properties, and metadata",
			"Connect your knowledge base directly to your search space",
			"Keep your search results up-to-date with latest Notion content",
			"Index your Notion workspace for enhanced search capabilities",
		],
		CONFLUENCE_CONNECTOR: [
			"Search through all your Confluence pages and spaces",
			"Access page content, comments, and attachments",
			"Connect your team's documentation directly to your search space",
			"Keep your search results up-to-date with latest Confluence content",
			"Index your Confluence workspace for enhanced search capabilities",
		],
		BOOKSTACK_CONNECTOR: [
			"Search through all your BookStack pages and books",
			"Access page content, chapters, and documentation",
			"Connect your documentation directly to your search space",
			"Keep your search results up-to-date with latest BookStack content",
			"Index your BookStack instance for enhanced search capabilities",
		],
		GITHUB_CONNECTOR: [
			"Search through code, issues, and documentation from GitHub repositories",
			"Access repository content, pull requests, and discussions",
			"Connect your codebase directly to your search space",
			"Keep your search results up-to-date with latest GitHub content",
			"Index your GitHub repositories for enhanced search capabilities",
		],
		JIRA_CONNECTOR: [
			"Search through all your Jira issues and tickets",
			"Access issue descriptions, comments, and project data",
			"Connect your project management directly to your search space",
			"Keep your search results up-to-date with latest Jira content",
			"Index your Jira projects for enhanced search capabilities",
		],
		CLICKUP_CONNECTOR: [
			"Search through all your ClickUp tasks and projects",
			"Access task descriptions, comments, and project data",
			"Connect your task management directly to your search space",
			"Keep your search results up-to-date with latest ClickUp content",
			"Index your ClickUp workspace for enhanced search capabilities",
		],
		LUMA_CONNECTOR: [
			"Search through all your Luma events",
			"Access event details, descriptions, and attendee information",
			"Connect your events directly to your search space",
			"Keep your search results up-to-date with latest Luma content",
			"Index your Luma events for enhanced search capabilities",
		],
		CIRCLEBACK_CONNECTOR: [
			"Automatically receive meeting notes, transcripts, and action items",
			"Access meeting details, attendees, and insights",
			"Search through all your Circleback meeting records",
			"Real-time updates via webhook integration",
			"No manual indexing required - meetings are added automatically",
		],
		OBSIDIAN_CONNECTOR: [
			"Search through all your Obsidian notes and knowledge base",
			"Access note content with YAML frontmatter metadata preserved",
			"Wiki-style links ([[note]]) and #tags are indexed",
			"Connect your personal knowledge base directly to your search space",
			"Incremental sync - only changed files are re-indexed",
			"Full support for your vault's folder structure",
		],
	};

	return benefits[connectorType] || null;
}
