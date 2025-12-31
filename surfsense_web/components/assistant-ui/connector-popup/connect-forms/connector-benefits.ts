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
		// Add other connectors as needed
		// GITHUB_CONNECTOR: [...],
	};

	return benefits[connectorType] || null;
}

