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
		// Add other connectors as needed
		// GITHUB_CONNECTOR: [...],
	};

	return benefits[connectorType] || null;
}

